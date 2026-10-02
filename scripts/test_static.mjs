import ts from 'typescript';
import {readFileSync,writeFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const code=ts.transpileModule(readFileSync('src/static-engine.ts','utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText;
writeFileSync('.test-artifacts/static-engine.mjs',code);
const {screen,csv}=await import('../.test-artifacts/static-engine.mjs');
const fixtures=JSON.parse(readFileSync('.test-artifacts/parity.json','utf8'));
for(const {snapshot,options,expected} of fixtures){const actual=screen(snapshot,options);assert.deepEqual(actual,expected);assert.equal(csv(actual).split('\r\n').length,actual.results.length+2)}
console.log(`${fixtures.length} Python / browser parity cases passed`);
