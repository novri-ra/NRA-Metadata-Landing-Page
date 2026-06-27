  // ==========================================
  // 7. PROMPT PRESETS (Save, Load, Delete)
  // ==========================================
  const presetNameInput = document.getElementById('presetNameInput');
  const savePresetBtn = document.getElementById('savePresetBtn');
  const presetSelect = document.getElementById('presetSelect');
  const loadPresetBtn = document.getElementById('loadPresetBtn');
  const deletePresetBtn = document.getElementById('deletePresetBtn');

  function loadPresetsList() {
    chrome.storage.local.get(['promptPresets'], (result) => {
      const presets = result.promptPresets || {};
      const presetKeys = Object.keys(presets);
      presetSelect.innerHTML = '<option value="">-- Load Preset --</option>';
      presetKeys.sort().forEach((key) => {
        const option = document.createElement('option');
        option.value = key;
        option.textContent = key;
        presetSelect.appendChild(option);
      });
    });
  }

  function savePreset() {
    const name = presetNameInput.value.trim();
    if (!name) return alert('Masukkan nama preset terlebih dahulu!');
    const promptText = promptInput.value.trim();
    if (!promptText) return alert('Prompt text kosong! Tidak ada yang bisa disimpan.');
    chrome.storage.local.get(['promptPresets'], (result) => {
      const presets = result.promptPresets || {};
      if (presets[name] !== undefined) {
        if (!confirm('Preset "'+name+'" sudah ada. Timpa dengan yang baru?')) return;
      }
      presets[name] = promptText;
      chrome.storage.local.set({ promptPresets: presets }, () => {
        console.log('[Canva Auto Prompter] ✅ Preset "'+name+'" berhasil disimpan.');
        presetNameInput.value = '';
        loadPresetsList();
        savePresetBtn.textContent = '✅ Saved!';
        setTimeout(() => savePresetBtn.textContent = '💾 Save', 1500);
      });
    });
  }

  function loadPreset() {
    const selectedKey = presetSelect.value;
    if (!selectedKey) return alert('Pilih preset terlebih dahulu dari dropdown!');
    chrome.storage.local.get(['promptPresets'], (result) => {
      const presets = result.promptPresets || {};
      const promptText = presets[selectedKey];
      if (promptText) {
        promptInput.value = promptText;
        chrome.storage.local.set({ savedPromptText: promptText });
        const lines = promptText.split('\n').filter(p => p.trim().length > 0);
        if (progressText) progressText.textContent = 'Progress: '+lines.length+' prompts loaded from preset';
        console.log('[Canva Auto Prompter] 📂 Preset "'+selectedKey+'" berhasil dimuat.');
        loadPresetBtn.textContent = '✅ Loaded!';
        setTimeout(() => loadPresetBtn.textContent = '📂 Load', 1500);
      } else {
        alert('Preset "'+selectedKey+'" tidak ditemukan.');
      }
    });
  }

  function deletePreset() {
    const selectedKey = presetSelect.value;
    if (!selectedKey) return alert('Pilih preset yang ingin dihapus dari dropdown!');
    if (!confirm('Hapus preset "'+selectedKey+'" secara permanen?')) return;
    chrome.storage.local.get(['promptPresets'], (result) => {
      const presets = result.promptPresets || {};
      delete presets[selectedKey];
      chrome.storage.local.set({ promptPresets: presets }, () => {
        console.log('[Canva Auto Prompter] 🗑️ Preset "'+selectedKey+'" berhasil dihapus.');
        loadPresetsList();
        deletePresetBtn.textContent = '✅ Deleted!';
        setTimeout(() => deletePresetBtn.textContent = '🗑️ Del', 1500);
      });
    });
  }

  if (savePresetBtn) savePresetBtn.addEventListener('click', savePreset);
  if (loadPresetBtn) loadPresetBtn.addEventListener('click', loadPreset);
  if (deletePresetBtn) deletePresetBtn.addEventListener('click', deletePreset);
  if (presetNameInput) {
    presetNameInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); savePreset(); }
    });
  }
  loadPresetsList();
