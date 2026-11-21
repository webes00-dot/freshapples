const TYPES = new Set(['Store correction','Missing retailer','Menu URL','Product or price correction','Strain or brand correction','Business classification / badge correction','Other feedback']);
export async function onRequestPost({request,env}) {
  const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});
  if(!env.GITHUB_FEEDBACK_TOKEN)return json({error:'Feedback intake is not configured yet. Please try again later.'},503);
  if(Number(request.headers.get('content-length')||0)>16000)return json({error:'Submission too large.'},413);
  let data;try{data=await request.json()}catch{return json({error:'Invalid submission.'},400)}
  if(data.website)return json({ok:true},200);
  const type=String(data.type||'').trim(),name=String(data.retailer||'').trim(),url=String(data.url||'').trim(),details=String(data.details||'').trim(),contact=String(data.contact||'').trim();
  if(!TYPES.has(type)||details.length<12||details.length>4000||name.length>180||url.length>500||contact.length>180)return json({error:'Please check the required fields and lengths.'},400);
  if(url&&!/^https?:\/\//i.test(url))return json({error:'Please enter a valid website URL.'},400);
  const classification=String(data.classification||'').trim(),classificationStatus=String(data.classification_status||'').trim();
  if(!['','SEA','MN Local','Tribal','Corporate'].includes(classification)||!['','Yes','No','Unknown'].includes(classificationStatus))return json({error:'Invalid classification selection.'},400);
  const ip=request.headers.get('CF-Connecting-IP')||'unknown';
  if(env.FEEDBACK_KV){const key='feedback:'+ip;const n=Number(await env.FEEDBACK_KV.get(key)||0);if(n>=5)return json({error:'Submission limit reached. Please try again later.'},429);await env.FEEDBACK_KV.put(key,String(n+1),{expirationTtl:3600})}
  const lines=['**Type:** '+type,'**Retailer / strain:** '+(name||'Not provided'),'**Source URL:** '+(url||'Not provided'),'**Classification:** '+(classification||'Not applicable'),'**Suggested classification status:** '+(classificationStatus||'Not applicable'),'**Reply contact (optional):** '+(contact||'Not provided'),'','### Submitted details',details,'','_Community submission; unverified until reviewed. Do not publish automatically._'];
  const response=await fetch('https://api.github.com/repos/rcwm56283/mntrees/issues',{method:'POST',headers:{'Authorization':'Bearer '+env.GITHUB_FEEDBACK_TOKEN,'Accept':'application/vnd.github+json','Content-Type':'application/json','User-Agent':'MNtrees-feedback'},body:JSON.stringify({title:'[Community feedback] '+type+(name?' — '+name:''),body:lines.join('\n')})});
  if(!response.ok){return json({error:'Unable to save submission. Please try again later.'},502)}
  const issue=await response.json();return json({ok:true,reference:'#'+issue.number});
}
export function onRequestGet(){return new Response('Method not allowed',{status:405})}
