const TYPES = new Set(['Store correction','Missing retailer','Menu URL','Product or price correction','Strain or brand correction','Business classification / badge correction','Other feedback']);
export async function onRequestPost({request,env}) {
  const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});
  if(!env.REVIEWS_DB)return json({error:'Feedback intake is not configured yet. Please try again later.'},503);
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
  const id=crypto.randomUUID();
  try{
    await env.REVIEWS_DB.prepare(
      'INSERT INTO feedback (id, type, retailer_or_strain, source_url, classification, classification_status, details, contact) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
    ).bind(id,type,name||null,url||null,classification||null,classificationStatus||null,details,contact||null).run();
  }catch{
    return json({error:'Unable to save submission. Please try again later.'},502);
  }
  return json({ok:true,reference:'#'+id},201);
}
export function onRequestGet(){return new Response('Method not allowed',{status:405})}
