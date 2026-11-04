const $ = id => document.getElementById(id);
let reels = [], selected = null, lastLibrary = '', active = false, toastTimer;
function toast(message) { $('toast').textContent = message; $('toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').hidden = true, 2500); }
function draftKey() { return `motivation-draft:${selected}`; }
function selectReel(id) {
  selected = id;
  const reel = reels.find(r => r.id === id);
  if (!reel) return;
  let draft = {};
  try { draft = JSON.parse(localStorage.getItem(draftKey()) || '{}'); } catch {}
  for (const field of ['title', 'description', 'hashtags']) {
    const original = field === 'hashtags' ? (reel.hashtags || []).join(' ') : reel[field] || '';
    $(field).value = draft[field] ?? original;
  }
  $('narration').textContent = reel.narration || '';
  $('detail').hidden = false;
  $('detail').classList.toggle('landscape', reel.format === 'youtube');
  $('download-video').textContent = reel.format === 'youtube' ? '↓ Download YouTube video' : '↓ Download reel';
  $('download-script').hidden = reel.format !== 'youtube';
  $('download-script').href = `/media/${encodeURIComponent(id)}/script`;
  $('video').hidden = !reel.available;
  $('missing').hidden = reel.available;
  $('download-video').hidden = !reel.available;
  if (reel.available) $('video').src = `/media/${encodeURIComponent(id)}/video`;
  else { $('video').pause(); $('video').removeAttribute('src'); $('video').load(); }
  $('download-video').href = `/media/${encodeURIComponent(id)}/video?download=1`;
  $('download-caption').href = `/media/${encodeURIComponent(id)}/caption`;
  $('download-metadata').href = `/media/${encodeURIComponent(id)}/metadata`;
  document.querySelectorAll('.reel').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.id === id)));
}
for (const field of ['title', 'description', 'hashtags']) $(field).addEventListener('input', () => {
  try { localStorage.setItem(draftKey(), JSON.stringify(Object.fromEntries(['title', 'description', 'hashtags'].map(k => [k, $(k).value])))); } catch { toast('Browser storage unavailable; copy your edits before leaving.'); }
});
async function copy(text) {
  try { await navigator.clipboard.writeText(text); toast('Copied to clipboard'); }
  catch { toast('Clipboard unavailable. Select the text and copy manually.'); }
}
document.querySelectorAll('[data-copy]').forEach(b => b.addEventListener('click', () => copy($(b.dataset.copy).value)));
$('copy-all').addEventListener('click', () => copy(['title', 'description', 'hashtags'].map(k => $(k).value).join('\n\n')));
document.querySelectorAll('[data-topic]').forEach(b => b.addEventListener('click', () => { $('topic').value = b.dataset.topic; $('topic').focus(); }));
function render(state) {
  reels = state.reels;
  const signature = JSON.stringify(reels);
  if (signature !== lastLibrary) {
    lastLibrary = signature;
    $('count').textContent = `${reels.length} video${reels.length === 1 ? '' : 's'}`;
    $('empty').hidden = reels.length > 0;
    $('library').replaceChildren(...reels.map(reel => {
      const button = document.createElement('button'); button.className = 'reel'; button.dataset.id = reel.id;
      button.setAttribute('aria-pressed', String(reel.id === selected));
      const meta = document.createElement('small'); meta.textContent = `${reel.format === 'youtube' ? '10 MIN · 16:9' : '30 SEC · 9:16'} / ${reel.reel_type || 'motivation'} / ${reel.mood || 'build'}${reel.available ? '' : ' / MISSING'}`;
      const title = document.createElement('strong'); title.textContent = reel.title || 'Untitled reel';
      button.append(meta, title); button.addEventListener('click', () => selectReel(reel.id)); return button;
    }));
    if (!selected && reels.length) selectReel(reels[0].id);
  }
  const job = state.jobs.find(j => j.status === 'running') || state.jobs[0];
  active = job?.status === 'running';
  $('generate').disabled = active;
  updateGenerateLabel();
  $('job-panel').hidden = !job;
  if (job) {
    $('job-status').textContent = active ? 'Your story is taking shape' : job.status === 'complete' ? 'Your video is ready' : 'Generation stopped';
    $('job-spinner').hidden = !active;
    const lines = job.log.trim().split('\n').filter(Boolean);
    $('job-message').textContent = job.error || (active ? lines.at(-1) || 'Starting the local generator…' : job.status === 'complete' ? 'Preview your video, then copy your caption below.' : 'Check the log below, resolve the issue, and generate again.');
    $('job-log').textContent = job.log || 'Waiting for the generator…';
    if (job.status === 'complete' && job.reel_id && sessionStorage.getItem('last-complete-job') !== job.id) {
      sessionStorage.setItem('last-complete-job', job.id);
      if (reels.some(r => r.id === job.reel_id)) selectReel(job.reel_id);
    }
  }
}
async function refresh() {
  try {
    const response = await fetch('/api/state'); if (!response.ok) throw new Error('Unable to load the workspace');
    render(await response.json()); $('form-error').textContent = '';
  } catch (error) { $('form-error').textContent = `${error.message}. Check that the dashboard server is running.`; }
}
$('generate-form').addEventListener('submit', async event => {
  event.preventDefault(); $('generate').disabled = true;
  try {
    const response = await fetch('/api/generate', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({format: $('video-format').value, reel_type: $('reel-type').value, topic: $('topic').value, mood: $('mood').value, visuals: $('visuals').value}) });
    const data = await response.json(); if (!response.ok) throw new Error(data.error || 'Could not start generation');
    await refresh();
  } catch (error) { $('form-error').textContent = error.message; $('generate').disabled = active; }
});
async function poll() { await refresh(); setTimeout(poll, 2500); }
poll();

const typeThemes = {
  city: {placeholder: 'A random city is picked for you. Add an optional angle, like architecture or street life…', topics: [['Architecture', 'Explore the selected city through its architecture and landmarks'], ['Street life', 'Capture the everyday atmosphere and streets of the selected city'], ['Surprise me', '']]},
  true_events: {placeholder: 'Choose Apollo 13, Miracle on the Hudson, or leave blank for a sourced incident…', topics: [['Surprise me', ''], ['Apollo 13', 'Apollo 13'], ['Hudson landing', 'Miracle on the Hudson']]},
  motivation: {placeholder: 'Showing up for yourself, even when motivation fades…', topics: [['Discipline', 'Building discipline through small daily habits'], ['Start again', 'Finding the courage to start again after failure'], ['Stay focused', 'Staying focused on your own journey']]},
  love: {placeholder: 'The little everyday moments that make love feel like home…', topics: [['Little moments', 'Love in the small everyday moments'], ['Trust', 'Building trust and understanding in a relationship'], ['Kindness', 'Expressing love through kindness and care']]},
  buddhism: {placeholder: 'Finding peace by letting go of what you cannot control…', topics: [['Mindfulness', 'Returning to the present moment with awareness'], ['Compassion', 'Meeting yourself and others with compassion'], ['Letting go', 'Finding peace through impermanence and letting go']]}
};
$('reel-type').addEventListener('change', () => {
  const type = $('reel-type').value;
  const theme = typeThemes[type];
  const localFootage = $('visuals').querySelector('option[value="footage"]');
  localFootage.disabled = type === 'city' || $('video-format').value === 'youtube';
  if (localFootage.disabled) $('visuals').value = 'ai';
  $('topic').value = '';
  $('topic').placeholder = theme.placeholder;
  document.querySelectorAll('[data-topic]').forEach((button, index) => {
    button.textContent = theme.topics[index][0]; button.dataset.topic = theme.topics[index][1];
  });
});

function updateGenerateLabel() {
  $('generate').firstChild.textContent = active ? 'Generating your video… ' : $('video-format').value === 'youtube' ? 'Generate YouTube video ' : 'Generate reel ';
}
$('video-format').addEventListener('change', () => {
  const long = $('video-format').value === 'youtube';
  $('long-info').hidden = !long;
  $('hero-format').textContent = long ? 'Longer stories.' : 'Short reels.';
  $('aspect-label').textContent = long ? '16:9' : '9:16';
  $('format-label').innerHTML = long ? 'YOUTUBE VIDEO<br>10 MINUTES · 1080p' : 'VERTICAL VIDEO<br>30 SECONDS · 720p';
  $('create-heading').textContent = long ? 'Your YouTube story starts here.' : 'Your next reel starts here.';
  $('scene-recipe').textContent = long ? '▧ 20 AI images, reused' : '▧ Five scenes';
  $('generation-help').textContent = long ? 'Writes ten connected sections and fits the full narration to ten minutes. Keep the server running until it finishes.' : 'Runs locally with your models. AI images can take several minutes.';
  const footage = $('visuals').querySelector('option[value="footage"]');
  footage.disabled = long || $('reel-type').value === 'city';
  if (footage.disabled) $('visuals').value = 'ai';
  updateGenerateLabel();
});
