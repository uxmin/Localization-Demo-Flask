let u=1,l="",c="desc",h="";const x=10;async function d(t=1){const n=new URLSearchParams({page:String(t),limit:String(x)});l&&(n.set("sort",l),n.set("direction",c)),h&&n.set("search",h);const r=await fetch(`/demo/internal/list?${n.toString()}`);if(!r.ok)return;const e=await r.json();console.log("json",e),Array.isArray(e.data)?w(e.data):console.error("Invalid data format:",e.data),E(e.meta?.page??1,e.meta?.total??0,e.meta?.limit??x)}function w(t){const n=document.getElementById("postTableBody");n.innerHTML="";const r={pending:{text:"Pending",classes:"text-gray-600 bg-gray-50 ring-gray-500/10"},in_progress:{text:"In Progress",classes:"text-yellow-800 bg-yellow-50 ring-yellow-600/20"},completed:{text:"Completed",classes:"text-green-700 bg-green-50 ring-green-600/20"}};t.forEach(e=>{const s=document.createElement("tr");s.className="bg-white border-b border-gray-200";const o=r[e.status]||r.pending;s.innerHTML=`
      <th scope="row" class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap">
        ${e.title}
      </th>
      <td class="px-6 py-4">${e.start_date}</td>
      <td class="px-6 py-4">${e.end_date}</td>
      <td class="px-6 py-4">
        <span class="inline-flex items-center px-2 py-1 text-xs font-medium rounded-md ring-1 ring-inset ${o.classes}">
          ${o.text}
        </span>
      </td>
      <td class="px-6 py-4 text-right">
        <a href="/demo/edit/${e.id}" class="font-medium text-blue-600 hover:underline">Edit</a>
      </td>
    `,n.appendChild(s)})}function E(t,n,r){const e=document.getElementById("paginationContainer");e.innerHTML="";const s=Math.ceil(n/r),o=5,g=(a,f,y=!1)=>{const p=document.createElement("li");return p.innerHTML=`
      <a href="#" ${y?'aria-current="page"':""}
         class="flex items-center justify-center h-10 px-4 leading-tight text-sm
                ${y?"text-blue-600 border border-blue-300 bg-blue-50":"text-gray-500 bg-white border border-gray-300 hover:bg-gray-100 hover:text-gray-700"}">
        ${a}
      </a>
    `,p.querySelector("a").addEventListener("click",b=>{b.preventDefault(),f!==u&&(u=f,d(u))}),p};if(t>1){const a=g("«",1);e.appendChild(a)}let m=Math.max(t-Math.floor(o/2),1),i=m+o-1;i>s&&(i=s,m=Math.max(i-o+1,1));for(let a=m;a<=i;a++)e.appendChild(g(a,a,a===t));if(t<s){const a=g("»",s);e.appendChild(a)}}document.addEventListener("DOMContentLoaded",()=>{d(1)});document.querySelectorAll("th a[data-sort]").forEach(t=>{t.addEventListener("click",n=>{n.preventDefault();const e=t.dataset.sort;l===e?c=c==="asc"?"desc":"asc":(l=e||"",c="asc"),d(1)})});document.querySelector("form")?.addEventListener("submit",t=>{t.preventDefault(),h=document.getElementById("simple-search").value.trim(),d(1)});
//# sourceMappingURL=work_history.js.map
