# Budget App

Django project using Python 3.12 and Django 5.2, managed with Apple Silicon Micromamba.

VS Code is configured to use the project environment. Open a new terminal in VS Code and run:

```sh
python manage.py runserver
```

Visit http://127.0.0.1:8000/ to see Django's starter page.

From any terminal in this folder, you can also run:

```sh
.conda/bin/python manage.py runserver
```

The Django package is named `budget_app`. The initial SQLite database migrations have been applied.

Settings come from the environment; copy `.env.example` to `.env` for local work. With `DJANGO_DEBUG=1` the app falls back to development defaults, so an empty `.env` is enough to get started.

To recreate the environment with the bundled Micromamba:

```sh
.tools/bin/micromamba --no-rc -r "$PWD/.mamba" create -y -p "$PWD/.conda" -f environment.yml
```

## React budget pages

- `/`: Teresa's available budget, spending by category, and a quick purchase form.
- `/workspace/`: Edit budget amounts, reserve, owner, title, and date range; browse, search, add, edit, or delete spending; experiment with hypothetical amounts without saving them.

The budget starts at zero. Set the real amount and dates in the workspace. All amounts are USD. Spending outside the selected dates stays in the ledger but does not reduce this period's balance. The reserve is subtracted from the amount available to spend. Records are saved in the Django SQLite database and shared across devices that access this server.

React source lives in `frontend/src/`. Vite bundles it into a single self-contained JavaScript file plus one stylesheet under `static/frontend/`, which Django serves. Build output is not committed — a fresh clone has to build once before Django can render a page:

```sh
cd frontend
npm install
npm run build
```

Filenames carry a content hash (`app.<hash>.js`). The Django template resolves them through Vite's `manifest.json` using the `{% frontend_assets %}` tag in [budget/templatetags/frontend.py](budget/templatetags/frontend.py), so a deploy can never leave a browser running a cached older bundle.

Run Django from the project folder for phone access on the same Wi-Fi:

```sh
python manage.py runserver 0.0.0.0:8001
```

The app is behind a single shared login. Locally, create one with `python manage.py createsuperuser`; on PythonAnywhere it is provisioned from `BUDGET_ADMIN_USER` / `BUDGET_ADMIN_PASSWORD` (see **Deployment** below). Anyone holding that password can view and edit the budget.

## Actual and theoretical monthly budgets

The workspace has two saved slots, **Actual** and **Theoretical**, with editable tables for monthly income, credit-card minimum payments and outstanding balances, and recurring expenses. Work insurance has separate premium, contribution percentage, and start-month inputs. Theoretical changes do not alter actual values or the spending log; “Copy saved actual” replaces the theoretical draft, which you can then save.

Monthly available money is income minus card minimums, recurring expenses, applicable insurance contribution, reserve, and other spending recorded in the selected month. Theoretical plans can also subtract a hypothetical extra purchase. Card balances are informational, not an additional monthly deduction. Insurance begins in the selected start month and is rounded to cents; monthly costs are not prorated.

Enter take-home income **before** the work-insurance deduction modeled here, so insurance is counted once. Use the spending log for purchases beyond the required bills in the tables. Comparisons use the same selected month and recorded spending on both sides. Changing a budget month selects a monthly view; it does not create a historical saved budget.

Existing budget funds were retained as an income row named “Existing budget amount.” Replace that label/amount with your real income sources as needed. Monthly plan saves detect stale edits from another window instead of silently overwriting them.



## Deployment

The app deploys to a PythonAnywhere web app. GitHub Actions builds the frontend, collects static files, uploads everything over the PythonAnywhere API, reloads the web app, and asks it to run migrations. The free tier gives CI no shell, so every step goes through the REST API — see [deploy/pythonanywhere_deploy.py](deploy/pythonanywhere_deploy.py).

### Workflows

| Workflow | Trigger | What it does |
| --- | --- | --- |
| [ci.yml](.github/workflows/ci.yml) | every push and pull request | frontend tests, bundle build, `collectstatic`, backend tests, `check --deploy` |
| [deploy.yml](.github/workflows/deploy.yml) | push to `main`, or manually | runs CI, then uploads, reloads, migrates, and health-checks |

A failing CI run blocks the deploy. Use **Run workflow** on the deploy action with *force static* ticked after upgrading Django, which changes the contents of the admin's static files without changing their names.

### One-time PythonAnywhere setup

1. **Web app** — on the Web tab, *Add a new web app* → *Manual configuration* → Python 3.12. (Manual, not the Django option: this project brings its own code.)
2. **Virtualenv** — in a Bash console:
   ```sh
   mkvirtualenv --python=/usr/bin/python3.12 budget-app
   pip install Django==5.2.17
   mkdir -p ~/budget-app ~/budget-data
   ```
   Put `/home/YOURNAME/.virtualenvs/budget-app` in the web app's *Virtualenv* field.
3. **WSGI file** — replace the contents of the web app's WSGI configuration file with [deploy/wsgi_pythonanywhere.py](deploy/wsgi_pythonanywhere.py), filling in every `CHANGE-ME`. This is where the deployed app's secrets live.
4. **Static files** — add one mapping on the Web tab:

   | URL | Directory |
   | --- | --- |
   | `/static/` | `/home/YOURNAME/budget-app/staticfiles/` |
5. **API token** — Account → *API token* → create one.
6. Click **Reload**. Visiting the site now gives an error until the first deploy uploads the code — that is expected.

### GitHub configuration

Repository → Settings → Secrets and variables → Actions:

| Secret | Value |
| --- | --- |
| `PA_USERNAME` | your PythonAnywhere username |
| `PA_API_TOKEN` | the API token from step 5 |
| `PA_DOMAIN` | `yourname.pythonanywhere.com` |
| `DEPLOY_TOKEN` | a random string; must match `DEPLOY_TOKEN` in the WSGI file |

Optional repository *variables*: `PA_HOST` (`eu.pythonanywhere.com` for EU accounts) and `PA_PROJECT_DIR` (defaults to `/home/$PA_USERNAME/budget-app`).

Generate the deploy token with:

```sh
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### What a deploy touches

Uploaded: `manage.py`, `requirements.txt`, `budget/`, `budget_app/`, `templates/`, and the collected `staticfiles/`. Static files whose paths already exist on the server are skipped, since their names are content-hashed.

Pruned: stale files under `staticfiles/` only. `db.sqlite3` and `.env` are never deleted, and the recommended `BUDGET_DB_PATH` puts the database outside the deployed tree entirely.

Not uploaded: frontend sources, CI config, this README. Deleting a Python module from the repo does not delete it from the server — remove it by hand in a PythonAnywhere console.

Migrations run through `POST /_deploy/finalize/`, which is a 404 unless the request carries the matching `DEPLOY_TOKEN`. It only ever runs `migrate` and `bootstrap_admin`. Leave `DEPLOY_TOKEN` unset on the server to disable the hook entirely and run migrations by hand instead.

### Checks

```sh
python manage.py test budget          # backend, including access control
npm test --prefix frontend            # frontend calculations
python manage.py check --deploy       # production settings
DEPLOY_DRY_RUN=1 python deploy/pythonanywhere_deploy.py   # list what a deploy would upload
```
