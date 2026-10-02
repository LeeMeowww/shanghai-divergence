import {defineConfig} from 'vite';
export default defineConfig({resolve:{preserveSymlinks:true},build:{rollupOptions:{output:{manualChunks:{charts:['echarts']}}}},server:{proxy:{'/api':'http://127.0.0.1:8765'}}});
