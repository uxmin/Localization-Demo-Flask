async function e(t,o){try{const r=await fetch(t,{method:"POST",body:o});if(!r.ok)throw new Error(`HTTP error! status: ${r.status}`);return await r.json()}catch(r){throw console.error("Fetch error: ",r),r}}export{e as f};
//# sourceMappingURL=utils_api.js.map
