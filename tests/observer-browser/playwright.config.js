const {defineConfig}=require('@playwright/test');
const {execFileSync}=require('node:child_process');
const path=require('node:path');
const root=path.resolve(__dirname,'../..');
const head=execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim();
if(process.env.OBSERVER_EXPECTED_HEAD_SHA && process.env.OBSERVER_EXPECTED_HEAD_SHA!==head)
  throw Error('Observer checkout does not match the requested exact head');
module.exports=defineConfig({
  testDir:__dirname,
  testMatch:'observer.spec.js',
  outputDir:path.join(__dirname,'.artifacts/test-results'),
  fullyParallel:false,
  workers:1,
  retries:0,
  forbidOnly:true,
  timeout:30000,
  expect:{timeout:5000},
  metadata:{head,expectedHead:process.env.OBSERVER_EXPECTED_HEAD_SHA||null,fixtureOnly:true},
  reporter:[['list'],['json',{outputFile:path.join(__dirname,'.artifacts/results.json')}],['html',{outputFolder:path.join(__dirname,'.artifacts/report'),open:'never'}]],
  use:{browserName:'chromium',headless:true,deviceScaleFactor:1,locale:'en-US',timezoneId:'UTC',colorScheme:'dark',reducedMotion:'reduce',serviceWorkers:'block',trace:'retain-on-failure',screenshot:'only-on-failure'},
  projects:[
    {name:'desktop-1440x900',use:{viewport:{width:1440,height:900}}},
    {name:'mobile-390x844',use:{viewport:{width:390,height:844},isMobile:true,hasTouch:true}},
    {name:'landscape-844x390',use:{viewport:{width:844,height:390},isMobile:true,hasTouch:true}}
  ]
});
