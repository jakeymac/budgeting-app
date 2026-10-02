import {defineConfig} from 'vite';

// The React app ships as one self-contained JS bundle plus one stylesheet,
// written straight into Django's static tree. Filenames carry a content hash
// and are resolved through manifest.json by the {% frontend_assets %} template
// tag, so a deploy can never leave a browser on a cached older bundle.
export default defineConfig({
  base: '/static/frontend/',
  build: {
    outDir: '../static/frontend',
    emptyOutDir: true,
    manifest: 'manifest.json',
    sourcemap: false,
    target: 'es2020',
    rollupOptions: {
      input: 'src/main.jsx',
      output: {
        entryFileNames: 'app.[hash].js',
        chunkFileNames: 'chunk.[hash].js',
        assetFileNames: 'app.[hash].[ext]',
      },
    },
  },
});
