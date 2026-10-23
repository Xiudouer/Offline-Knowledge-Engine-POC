'use strict';
let token = '';
const byId = id => document.getElementById(id);
const messages = {
  unauthenticated:'访问令牌不正确，请重新连接。', local_model_missing:'本地模型缺失，请校验离线资源后重新启动。',
  local_model_unavailable:'本地模型服务尚未就绪或暂时不可用，请稍后重试。',
  local_database_unavailable:'本地知识库暂时不可用，请检查容器状态后重试。',
  embedding_model_changed_reindex_required:'向量模型已变化，请在新实例中重新导入原始文档。',
  no_extractable_text_ocr_not_included:'没有可提取的文字。扫描 PDF 请先在本地完成 OCR。',
  local_parser_timeout:'解析超过时间限制，请拆分文件后重试。',
  local_parser_failed:'本地解析未完成，请检查文件格式或拆分文件后重试。',
  document_too_large:'文件超过 20 MiB，请拆分后重试。', request_size_limit:'请求过大，请缩小文件或问题。',
  unsupported_or_oversize_document:'文件格式不支持、为空或超过大小限制。',
  poc_chunk_capacity_reached:'已达到 POC 容量限制，请移除旧文档或建立新实例。'
};
async function request(path, body, extra = {}) {
  const headers = {Authorization: 'Bearer ' + token, ...extra};
  if (body && !(body instanceof File)) headers['Content-Type'] = 'application/json';
  const response = await fetch(path, {method: body ? 'POST' : 'GET', headers,
    body: body instanceof File ? body : body ? JSON.stringify(body) : undefined, cache: 'no-store', redirect: 'error'});
  const value = await response.json();
  if (!response.ok) throw new Error(messages[value.error] || '本机服务未就绪或文件无法处理，请检查文件和容器状态。');
  return value;
}
async function documents() {
  const data = await request('/api/documents');
  byId('documents').replaceChildren();
  for (const item of data.documents) {
    const li = document.createElement('li');
    li.textContent = item.filename + ' · ' + item.chunks + ' 个片段';
    const remove = document.createElement('button'); remove.textContent = '移除';
    remove.addEventListener('click', async () => {if (!confirm('从本机索引移除此文档？原始文件不受影响。')) return;
      try {await request('/api/delete', {id:item.id}); await documents();} catch(e) {byId('upload-status').textContent=e.message;}});
    li.append(remove); byId('documents').append(li);
  }
}
byId('connect').addEventListener('click', async () => {
  const button=byId('connect'); button.disabled=true; token=byId('token').value.trim();
  try {await request('/api/status'); byId('status').textContent='已连接 · 本地隔离模式'; byId('token').value=''; byId('login').hidden=true; await documents();}
  catch(e) {token=''; byId('login').hidden=false; byId('status').textContent=e.message;} finally {button.disabled=false;}
});
byId('upload').addEventListener('click', async () => {
  const file=byId('file').files[0]; if (!file) {byId('upload-status').textContent='请先选择本地文件。';return;}
  if (file.size>20*1024*1024) {byId('upload-status').textContent='文件超过 20 MiB。';return;}
  byId('upload').disabled=true; byId('upload-status').textContent='正在本机解析、向量化和入库；CPU 模式可能需要几分钟……';
  try {const result=await request('/api/ingest',file,{'X-Filename':encodeURIComponent(file.name)});
    byId('upload-status').textContent=(result.duplicate?'文档已存在：':'已完成：')+result.chunks+' 个片段。';await documents();}
  catch(e){byId('upload-status').textContent=e.message;}finally{byId('upload').disabled=false;}
});
byId('ask').addEventListener('click', async () => {
  byId('ask').disabled=true; byId('answer').textContent='正在本机检索并生成回答……';byId('sources').replaceChildren();
  try {const result=await request('/api/ask',{question:byId('question').value});byId('answer').textContent=result.answer;
    for(const source of result.sources){const box=document.createElement('details');box.className='source';
      const title=document.createElement('summary');title.textContent='['+source.citation+'] '+source.filename+' · '+(source.locator.page?'第 '+source.locator.page+' 页':'文本段')+' · 字符 '+source.locator.start+'–'+source.locator.end;
      const text=document.createElement('p');text.textContent=source.content;box.append(title,text);byId('sources').append(box);}}
  catch(e){byId('answer').textContent=e.message;}finally{byId('ask').disabled=false;}
});
