import { defineConfig, loadEnv } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

// https://vitejs.dev/config/
export default defineConfig((command, mode) => {
  loadEnv(mode, process.cwd(), "VITE_")
  
  return {
    server: {
      host: '0.0.0.0',
      port: 8505,
    },
    plugins: [svelte()],
  }
})
