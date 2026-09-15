// Run with: node northway_crm/tests/test_inbox_frontend.cjs
// Exercise the actual inline handlers using an isolated DOM and fake HTTP responses.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../templates/whatsapp_inbox.html'), 'utf8');
const handlers = source.slice(source.indexOf('    let nextConversationPage'), source.indexOf('    // --- Media Logic ---'));
const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {innerHTML: '', value: '', scrollTop: 0, scrollHeight: 100,
    clientHeight: 100, classList: {add(){}, remove(){}}, querySelectorAll(){return []},
    insertAdjacentHTML(_, html){this.innerHTML += html;}});
  return elements.get(id);
}
const responses = [];
const urls = [];
const context = vm.createContext({console, URL, URLSearchParams, setTimeout, clearTimeout,
  setInterval, clearInterval, document: {hidden: false, getElementById: element}, window: {},
  fetch: async url => {urls.push(url); return {ok: true, status: 200, json: async () => responses.shift()};}});
vm.runInContext("let activeChat = {type: 'lead', id: 1}; let allConversations = []; let currentTab = 'all';" + handlers, context);
const message = (id, content) => ({id, content, timestamp: '2026-09-15T12:00:00', direction: 'in', status: 'sent'});
(async () => {
  responses.push({messages: [message(51, '<img onerror=alert(1)>')], oldest_id: 51, latest_id: 51, has_more: true});
  await vm.runInContext("loadMessages('lead', 1)", context);
  assert.match(element('chat-messages').innerHTML, /&lt;img onerror=alert\(1\)&gt;/);
  assert.match(element('chat-messages').innerHTML, /Carregar mensagens anteriores/);
  assert.doesNotMatch(urls.at(-1), /after_id/);
  responses.push({messages: [], status_updates: [{id: 51, status: 'sent'}]});
  element('chat-messages').innerHTML = 'audio currently playing';
  await vm.runInContext("loadMessages('lead', 1, true)", context);
  assert.match(urls.at(-1), /after_id=51/);
  assert.equal(element('chat-messages').innerHTML, 'audio currently playing');
  responses.push({messages: [message(50, 'older')], oldest_id: 50, latest_id: 50, has_more: false});
  await vm.runInContext('loadOlderMessages()', context);
  assert.match(urls.at(-1), /before_id=51/);
  assert.match(element('chat-messages').innerHTML, /older/);
  assert.match(element('chat-messages').innerHTML, /&lt;img/);
  const count = urls.length;
  context.document.hidden = true;
  await vm.runInContext("loadMessages('lead', 1, true)", context);
  assert.equal(urls.length, count);
  context.document.hidden = false;
  responses.push({conversations: [{id: 1, type: 'lead', phone: '123', name: '<script>bad</script>'}], next_page: 2});
  await vm.runInContext('loadConversations()', context);
  assert.match(element('conversation-list').innerHTML, /&lt;script&gt;bad/);
  assert.match(element('conversation-list').innerHTML, /Carregar mais conversas/);
  element('conversation-search').value = 'another';
  responses.push({conversations: [], next_page: null});
  await vm.runInContext('loadConversations()', context);
  assert.match(urls.at(-1), /q=another/);
  assert.match(element('conversation-list').innerHTML, /Nenhuma conversa/);
  console.log('PASS: inbox cursors, escaping, unchanged polling, hidden tabs, search and pagination');
})().catch(error => {console.error(error); process.exitCode = 1;});
