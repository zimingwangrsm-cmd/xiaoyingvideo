// Patch the existing tree so playing media and focused controls stay connected.
function key(node) {
  if(node.nodeType!==1)return '';
  return node.id || (node.dataset.block?'block:'+node.dataset.block:'') ||
    (node.dataset.suggestion?'suggestion:'+node.dataset.suggestion:'') ||
    (['VIDEO','AUDIO'].includes(node.tagName)?node.tagName+':'+node.getAttribute('src'):'');
}
function compatible(a,b){return a&&a.nodeType===b.nodeType&&(a.nodeType!==1||a.tagName===b.tagName)&&key(a)===key(b);}
function patch(node,fresh){
  if(node.nodeType!==1){if(node.nodeValue!==fresh.nodeValue)node.nodeValue=fresh.nodeValue;return;}
  for(const attr of [...node.attributes])if(!fresh.hasAttribute(attr.name))node.removeAttribute(attr.name);
  for(const attr of fresh.attributes)if(node.getAttribute(attr.name)!==attr.value)node.setAttribute(attr.name,attr.value);
  if(node.tagName==='INPUT'){
    if(node.type!=='file'&&node.value!==fresh.value)node.value=fresh.value;
    node.checked=fresh.checked;
  }
  if(node.tagName==='TEXTAREA'){
    if(node.value!==fresh.value)node.value=fresh.value;
    return;
  }
  morphChildren(node,fresh);
  if(node.tagName==='SELECT'&&node.value!==fresh.value)node.value=fresh.value;
}
export function morphChildren(parent,freshParent){
  const old=[...parent.childNodes],used=new Set();let cursor=parent.firstChild;
  for(const fresh of [...freshParent.childNodes]){
    const node=compatible(cursor,fresh)&&!used.has(cursor)?cursor:old.find(n=>!used.has(n)&&compatible(n,fresh));
    if(node){used.add(node);if(node!==cursor)parent.insertBefore(node,cursor);patch(node,fresh);cursor=node.nextSibling;}
    else{const created=fresh.cloneNode(true);parent.insertBefore(created,cursor);cursor=created.nextSibling;}
  }
  for(const node of old)if(!used.has(node))node.remove();
}
export function renderInto(parent,html){const template=document.createElement('template');template.innerHTML=html;morphChildren(parent,template.content);}
