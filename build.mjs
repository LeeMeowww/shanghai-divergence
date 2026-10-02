// In-process TypeScript transform also works on Windows hosts that disallow child binaries.
import {build} from 'vite';
import ts from 'typescript';
import {createRequire} from 'node:module';
import {dirname} from 'node:path';
const require=createRequire(import.meta.url);
const pages=process.env.BUILD_TARGET==='pages';
const aliases=Object.fromEntries(['zrender','tslib','scheduler'].map(name=>[name,dirname(require.resolve(name==='tslib'?name:name+'/package.json',{paths:[dirname(require.resolve('echarts/package.json')),dirname(require.resolve('react-dom/package.json'))]}))]));
await build({configFile:false,base:pages?'./':'/',publicDir:pages?'public-pages':false,resolve:{preserveSymlinks:true,alias:aliases},esbuild:false,
 plugins:[{name:'production-env',enforce:'pre',transform(code,id){if(pages&&id.replaceAll('\\','/').endsWith('/src/runtime.ts'))code=code.replace('STATIC_MODE = false','STATIC_MODE = true');if(/\.[cm]?[jt]sx?$/.test(id))return {code:code.replaceAll('process.env.NODE_ENV','"production"'),map:null}}},{name:'typescript-transpile',transform(code,id){if(/\/src\/.*\.tsx?$/.test(id.replaceAll('\\','/')))return {code:ts.transpileModule(code,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText,map:null}}}],
 build:{outDir:pages?'dist-pages':'dist',minify:false,cssMinify:false,rollupOptions:{output:{manualChunks:{charts:['echarts']}}}}});

