/**
 * Browser regression for import, replacement, and optimized-reference score refresh.
 * All food-service calls are mocked; requires a local dev server and isolated Chromium.
 * Start Vite on port 5185 and Chromium with --remote-debugging-port=9227 and a temporary
 * --user-data-dir, then run: node scripts/recipe-refresh.browser.mjs
 * Override APP_URL / BROWSER_DEBUG_URL for different local ports; TEST_LOCALE=fr-FR tests French.
 */
import assert from 'node:assert/strict';
const browserUrl = process.env.BROWSER_DEBUG_URL ?? 'http://127.0.0.1:9227';
const appUrl = process.env.APP_URL ?? 'http://127.0.0.1:5185';
const locale = process.env.TEST_LOCALE ?? 'en-US';
const labels = locale.startsWith('fr')
	? { add: 'Ajouter des ingrédients', better: 'Améliorer la recette', optimize: 'Optimiser' }
	: { add: 'Add ingredients', better: 'Make it better', optimize: 'Optimize' };
const tabs = await (await fetch(`${browserUrl}/json/list`)).json();
const socket = new WebSocket(tabs.find((t) => t.type === 'page').webSocketDebuggerUrl);
await new Promise((resolve) => socket.addEventListener('open', resolve, { once: true }));
let seq = 0;
const pending = new Map();
const exceptions = [];
socket.addEventListener('message', (event) => {
	const msg = JSON.parse(event.data);
	if (msg.id) {
		const cb = pending.get(msg.id);
		pending.delete(msg.id);
		if (msg.error) cb.reject(msg.error);
		else cb.resolve(msg.result);
	}
	if (msg.method === 'Runtime.exceptionThrown') exceptions.push(msg.params.exceptionDetails);
});
/** Send one DevTools command and pair its response by command ID. */
function call(method, params = {}) {
	return new Promise((resolve, reject) => {
		const id = ++seq;
		pending.set(id, { resolve, reject });
		socket.send(JSON.stringify({ id, method, params }));
	});
}
/** Evaluate in the page and surface browser exceptions as test failures. */
async function evaluate(expression) {
	const r = await call('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
	if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
	return r.result.value;
}
/** Wait for observable UI state with a bounded failure deadline. */
async function until(expression, label) {
	for (let i = 0; i < 100; i++) {
		if (await evaluate(expression)) return;
		await new Promise((r) => setTimeout(r, 150));
	}
	throw new Error('Timeout: ' + label + ' ' + (await evaluate('document.body.innerText')));
}
await call('Runtime.enable');
await call('Page.enable');
await call('Network.enable');
await call('Network.setExtraHTTPHeaders', { headers: { 'Accept-Language': locale } });
const injected = await call('Page.addScriptToEvaluateOnNewDocument', {
	source: `
Object.defineProperty(navigator, "language", {value: ${JSON.stringify(locale)}, configurable:true});
Object.defineProperty(navigator, "languages", {value: [${JSON.stringify(locale)}], configurable:true});
const originalFetch=window.fetch;
window.calls=[];
const send=value=>new Response(JSON.stringify(value),{headers:{'content-type':'application/json'}});
window.fetch=async (input,init)=>{
 const url=String(input instanceof Request ? input.url : input);
 if(!url.includes('/v1/') && !url.includes('openfoodfacts.org'))return originalFetch(input,init);
 const path=new URL(url,location.href); const body=init?.body?JSON.parse(init.body):null;
 window.calls.push({url:path.pathname,q:path.searchParams.get('q'),lang:path.searchParams.get('lang'),body});
 if(url.includes('/v1/parse_text')) return send({ingredients:[{codified_ingredient:'Yaourt au chocolat',taxonomy_id:'en:chocolate-yogurt',is_in_taxonomy:true,quantity_g:100}]});
 if(url.includes('/v1/ingredient-references')) {
  await new Promise(r=>setTimeout(r,150));
  const name=path.searchParams.get('q');const code=name==='Yaourt nature'?'19593':name==='Pomme'?'13000':'19580';
  return send({ciqual:{code,name:name+' CIQUAL'},agribalyse:{code,name:name+' Agribalyse'},source:'name_match'});
 }
 if(url.includes('/v1/nutrition/products')) {
  await new Promise(r=>setTimeout(r,250));
  const name=path.searchParams.get('q');const code=name==='Yaourt nature'?'333':name==='Pomme'?'222':'111';
  return send({foods:[{code:'rejected',name:'Unrelated product',automatic_match:false},{code,name:name+' OFF',automatic_match:true}]});
 }
 if(url.includes('/v1/green-score'))return send({numericScore:body.ingredients[0].agribalyseCode==='19593'?80:50,letterGrade:'B',missingIngredientIds:[]});
 if(url.includes('/v1/nutrition/analyze'))return send({status:'complete',nutri_score:{grade:body.ingredients[0].ciqual_code==='19593'?'a':'d',score:body.ingredients[0].ciqual_code==='19593'?0:12,components:{positive:[],negative:[]}},ingredients:[],diagnostics:[],assumptions:[],excluded_ingredients:[],excluded_weight_percent:0,additives:[],allergens:[]});
 if(url.includes('/v1/make-it-better/check')) {
  const recipe=body.recipe;window.reviewRecipe=recipe;
  const before=recipe.ingredients[0];const after={...before,name:'Yaourt nature',ciqual_code:'19593',barcode:null,agribalyse_code:'19593',codified_ingredient:null,labels:[],origin:null};window.reviewAfter=after;
  return send({suggestions:[{id:before.id+':ciqual:19593',ingredient_id:before.id,category:'ingredient',before,after,ciqual_name:'Yaourt nature CIQUAL',agribalyse_name:'Yaourt nature Agribalyse',green_score:{before:50,after:80,before_grade:'C',after_grade:'B',percent:60},nutri_score:{before:12,after:0,before_grade:'D',after_grade:'A',percent:100}}]});
 }
 if(url.includes('/v1/make-it-better/optimize'))return send({recipe:{...window.reviewRecipe,ingredients:[window.reviewAfter]}});
 return send({suggestions:[],foods:[],ingredients:[],origins:[]});
};
`
});
try {
	await call('Page.navigate', { url: `${appUrl}/score` });
	await until(
		`[...document.querySelectorAll('button')].some(b=>b.textContent.trim()===${JSON.stringify(labels.add)})`,
		'load'
	);
	await new Promise((r) => setTimeout(r, 2000));
	await evaluate(
		`[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(labels.add)}).click()`
	);
	await until(`!!document.querySelector('dialog[open] textarea')`, 'import dialog');
	await evaluate(
		`(()=>{const area=document.querySelector('dialog[open] textarea');area.value='100g Yaourt au chocolat';area.dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('dialog[open] form').requestSubmit()})()`
	);
	/** Assert all correspondences and the resulting environmental and nutrition requests. */
	async function checkRow(name, ciqual, barcode) {
		await until(
			`document.querySelector('input[id^="ingredient-product-"]')?.value===${JSON.stringify(name + ' OFF')} && ![...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(labels.better)})?.disabled`,
			'references for ' + name
		);
		await until(
			`window.calls.filter(c=>c.url==='/v1/nutrition/analyze').at(-1)?.body.ingredients[0].barcode===${JSON.stringify(barcode)} && window.calls.filter(c=>c.url==='/v1/green-score').at(-1)?.body.ingredients[0].agribalyseCode===${JSON.stringify(ciqual)}`,
			'scores for ' + name
		);
		const refs = await evaluate(
			`[...document.querySelectorAll('input[id^="ingredient-"]')].map(i=>({id:i.id,value:i.value}))`
		);
		assert(
			refs.some((i) => i.value === name + ' CIQUAL'),
			'Missing CIQUAL ' + JSON.stringify(refs)
		);
		assert(
			refs.some((i) => i.value === name + ' Agribalyse'),
			'Missing Agribalyse ' + JSON.stringify(refs)
		);
		assert.equal(
			await evaluate(
				`window.calls.filter(c=>c.url==='/v1/nutrition/analyze').at(-1).body.ingredients[0].ciqual_code`
			),
			ciqual
		);
		assert.equal(
			await evaluate(
				`window.calls.filter(c=>c.url==='/v1/ingredient-references' && c.q===${JSON.stringify(name)}).length`
			),
			1,
			'No duplicate reference lookup'
		);
		assert.equal(
			await evaluate(
				`window.calls.filter(c=>c.url==='/v1/ingredient-references' && c.q===${JSON.stringify(name)})[0].lang`
			),
			locale.split('-')[0]
		);
		console.log('PASS ' + name + ': all three references and both score requests; one lookup');
	}
	await checkRow('Yaourt au chocolat', '19580', '111');
	await evaluate(
		`(()=>{const input=document.querySelector('input[id^="ingredient-name-"]');input.focus();input.value='Pomme';input.dispatchEvent(new Event('input',{bubbles:true}));input.blur()})()`
	);
	await checkRow('Pomme', '13000', '222');
	await evaluate(
		`[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(labels.better)}).click()`
	);
	await until(
		`document.querySelector('dialog[open]')?.innerText.includes('+60.0%')`,
		'suggestions'
	);
	await evaluate(
		`[...document.querySelector('dialog[open]').querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(labels.optimize)}).click()`
	);
	await until(`!document.querySelector('dialog[open]')`, 'close optimized dialog');
	await checkRow('Yaourt nature', '19593', '333');
	await until(
		`!document.querySelector('[aria-live="polite"][aria-busy="true"]')`,
		'score loading finished'
	);
	assert.equal(
		await evaluate(`!!document.querySelector('img[src*="nutri-score-a"]')`),
		true,
		'Updated Nutri-Score visible'
	);
	assert(
		(await evaluate('document.body.innerText')).includes('80.0'),
		'Updated Green-Score visible'
	);
	assert.equal(exceptions.length, 0, JSON.stringify(exceptions));
	console.log('PASS updated grades visible; no browser exceptions');
} finally {
	await call('Page.removeScriptToEvaluateOnNewDocument', { identifier: injected.identifier });
	socket.close();
}
