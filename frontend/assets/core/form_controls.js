(function () {
  window.NovelUiMethods = {
    escape(value) {
      return String(value ?? '').replace(/[&<>'"]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[ch]));
    },
    attr(value) {
      return this.escape(value);
    },
    basename(path) {
      const text = String(path || '').trim();
      if (!text) return '';
      const items = text.split(/\r?\n/).map(item => item.trim()).filter(Boolean);
      if (items.length > 1) return `${items.length} 个文件`;
      const cleaned = items[0].replace(/[\\/]+$/, '');
      const parts = cleaned.split(/[\\/]+/);
      return parts[parts.length - 1] || cleaned;
    },
    filePicker(inputId, value, buttonId, emptyText) {
      const name = this.basename(value);
      return `<input type="hidden" id="${this.attr(inputId)}" value="${this.attr(value || '')}" />
        <div class="file-picker ${name ? '' : 'empty'}" data-file-picker="${this.attr(inputId)}">
          <div class="file-meta"><span>已选择</span><strong id="${this.attr(inputId)}Name">${this.escape(name || emptyText || '未选择')}</strong></div>
          <button class="ghost-btn" id="${this.attr(buttonId)}" type="button">选择</button>
        </div>`;
    },
    updateFilePicker(inputId, path, emptyText) {
      const input = document.getElementById(inputId);
      if (input) input.value = path || '';
      const label = document.getElementById(`${inputId}Name`);
      if (label) label.textContent = this.basename(path) || emptyText || '未选择';
      const picker = document.querySelector(`[data-file-picker="${inputId}"]`);
      if (picker) picker.classList.toggle('empty', !this.basename(path));
    }
  };
})();
