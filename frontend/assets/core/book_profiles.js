(function () {
  window.NovelBookProfileMethods = {
    renderBookProfileFields(prefix, cfg) {
      const profiles = Array.isArray(this.state.config.bookProfiles) ? this.state.config.bookProfiles : [];
      const selectedId = cfg.bookProfileId || this.state.config.activeBookId || '';
      const selected = profiles.find((item) => item.id === selectedId);
      return `
        <div class="field"><label>小说来源</label>${this.filePicker(`${prefix}NovelFile`, selected?.novelFile || cfg.novelFile || '', `${prefix}ChooseNovel`, '选择小说来源')}</div>
        <div class="field"><label>番茄作品</label>
          <input type="hidden" id="${prefix}BookProfile" value="${this.attr(selectedId)}" />
          <div class="file-picker ${selected ? '' : 'empty'}" data-book-picker="${prefix}">
            <div class="file-meta"><span>已选择</span><strong id="${prefix}BookProfileName">${this.escape(selected?.name || (profiles.length ? '选择番茄作品' : '正在读取作品…'))}</strong></div>
            <button class="ghost-btn" id="${prefix}ChooseBook" type="button">选择</button>
          </div>
        </div>
        <input type="hidden" id="${prefix}BookName" value="${this.attr(selected?.name || cfg.expectedBookName || '')}" />
        <input type="hidden" id="${prefix}Url" value="${this.attr(selected?.chapterManageUrl || cfg.chapterManageUrl || '')}" />`;
    },
    bindBookProfileControls(prefix, section) {
      const button = document.getElementById(`${prefix}ChooseBook`);
      const picker = button?.closest('.file-picker');
      const profiles = Array.isArray(this.state.config.bookProfiles) ? this.state.config.bookProfiles : [];
      const options = profiles.length
        ? profiles.map((item) => ({ value: item.id, title: item.name }))
        : [{ value: '__refresh__', title: '正在读取作品…' }];
      this.bindFanqiePickerMenu(button, picker, options, async (profileId) => {
        if (profileId === '__refresh__') return this.refreshFanqieBooks(section);
        const oldId = this.state.config[section]?.bookProfileId || '';
        const pendingSource = oldId ? '' : (document.getElementById(`${prefix}NovelFile`)?.value || '');
        const result = await this.api.select_fanqie_book(profileId, pendingSource);
        if (!result?.ok) return this.toast(result?.message || '作品切换失败。', 'warning', section);
        this.state = await this.api.get_state();
        this.render();
      });
      this.refreshFanqieBooks(section);
    },
    async refreshFanqieBooks(section) {
      if (this._fanqieBooksLoading || this._fanqieBooksLoaded) return;
      if (!this.api.check_login_state || !await this.api.check_login_state()) return;
      this._fanqieBooksLoading = true;
      const result = await this.api.list_fanqie_books();
      this._fanqieBooksLoading = false;
      if (!result?.ok) return;
      this._fanqieBooksLoaded = true;
      this.state = await this.api.get_state();
      this.render();
    },
    async mapSelectedBookSource(prefix, section, path) {
      const profileId = document.getElementById(`${prefix}BookProfile`)?.value || '';
      if (!profileId || !path) return;
      const result = await this.api.select_fanqie_book(profileId, path);
      if (!result?.ok) return this.toast(result?.message || '小说来源绑定失败。', 'warning', section);
      this.state = await this.api.get_state();
      this.render();
    },
    validateBookProfilePayload(payload, page) {
      const profiles = Array.isArray(this.state.config.bookProfiles) ? this.state.config.bookProfiles : [];
      const profile = profiles.find((item) => item.id === payload.bookProfileId);
      const matches = profile && profile.name === payload.expectedBookName
        && profile.novelFile === payload.novelFile && profile.chapterManageUrl === payload.chapterManageUrl;
      if (matches && payload.novelFile) return true;
      this.toast('请选择番茄作品和小说来源。', 'warning', page);
      this.setHeaderStatus('请选择作品和小说来源', 'error');
      return false;
    },
  };
})();
