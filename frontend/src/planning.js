export function toCents(value) {
  const text = String(value);
  if (!/^\d{1,10}(\.\d{0,2})?$/.test(text)) throw new Error('Enter amounts with up to two decimal places.');
  const [whole, fraction = ''] = text.split('.');
  return Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
}
export function calculatePlan(plan, events) {
  if (!/^(?!0000)\d{4}-(0[1-9]|1[0-2])$/.test(plan.month)) throw new Error('Choose a budget month.');
  if (!/^(?!0000)\d{4}-(0[1-9]|1[0-2])$/.test(plan.insurance.start_month)) throw new Error('Choose an insurance start month.');
  const income = plan.incomes.reduce((s, row) => s + toCents(row.amount), 0);
  const expenses = plan.expenses.reduce((s, row) => s + toCents(row.amount), 0);
  let minimums = 0, debt = 0;
  for (const row of plan.cards) {
    const minimum = toCents(row.minimum), balance = toCents(row.balance);
    if (minimum > balance) throw new Error('A card’s monthly minimum cannot exceed its balance.');
    minimums += minimum; debt += balance;
  }
  const rate = toCents(plan.insurance.percentage);
  if (rate > 10000) throw new Error('Your contribution percentage must be between 0 and 100.');
  const premium = toCents(plan.insurance.premium);
  const contribution = Number((BigInt(premium) * BigInt(rate) + 5000n) / 10000n);
  const insurance = plan.month >= plan.insurance.start_month ? contribution : 0;
  const reserve = toCents(plan.reserve), extra = toCents(plan.extra_spending);
  const spending = events.filter(e => e.date.slice(0, 7) === plan.month).reduce((s, row) => s + toCents(row.amount), 0);
  const required = minimums + expenses + insurance;
  return {income, expenses, minimums, debt, contribution, insurance, reserve, extra, spending,
    required, discretionary: income-required-reserve, available: income-required-reserve-spending-extra};
}
