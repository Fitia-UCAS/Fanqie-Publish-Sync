(function () {
  window.NovelFanqieAccountMethods = {
    bindFanqiePickerMenu(button, picker, options, onSelect) {
      if (!button || !picker || picker.dataset.fanqiePickerBound === '1') return;
      picker.dataset.fanqiePickerBound = '1';
      picker.classList.add('source-file-picker');
      button.classList.add('source-picker-toggle');
      button.setAttribute('aria-haspopup', 'menu');
      button.setAttribute('aria-expanded', 'false');
      button.innerHTML = '<span>选择</span><span class="source-picker-caret" aria-hidden="true">▾</span>';

      const menu = document.createElement('div');
      menu.className = 'source-picker-menu';
      menu.setAttribute('role', 'menu');
      menu.hidden = true;

      options.forEach((option) => {
        const item = document.createElement('button');
        item.type = 'button';
        item.setAttribute('role', 'menuitem');
        item.dataset.pickerValue = option.value;
        item.textContent = option.title;
        menu.appendChild(item);
      });
      picker.appendChild(menu);

      const closeMenu = () => {
        menu.hidden = true;
        picker.classList.remove('source-picker-open');
        button.setAttribute('aria-expanded', 'false');
      };
      const openMenu = () => {
        document.querySelectorAll('.source-file-picker.source-picker-open').forEach((other) => {
          if (other !== picker && typeof other._fanqieClosePicker === 'function') {
            other._fanqieClosePicker();
          }
        });
        menu.hidden = false;
        picker.classList.add('source-picker-open');
        button.setAttribute('aria-expanded', 'true');
      };
      picker._fanqieClosePicker = closeMenu;

      button.addEventListener('click', (event) => {
        event.stopPropagation();
        if (menu.hidden) openMenu();
        else closeMenu();
      });
      menu.addEventListener('click', async (event) => {
        const option = event.target.closest('[data-picker-value]');
        if (!option) return;
        event.stopPropagation();
        closeMenu();
        await onSelect(option.dataset.pickerValue);
      });

      if (!this._fanqiePickerDocumentHandlersBound) {
        document.addEventListener('click', (event) => {
          document.querySelectorAll('.source-file-picker.source-picker-open').forEach((activePicker) => {
            if (!activePicker.contains(event.target) && typeof activePicker._fanqieClosePicker === 'function') {
              activePicker._fanqieClosePicker();
            }
          });
        });
        document.addEventListener('keydown', (event) => {
          if (event.key !== 'Escape') return;
          document.querySelectorAll('.source-file-picker.source-picker-open').forEach((activePicker) => {
            if (typeof activePicker._fanqieClosePicker === 'function') activePicker._fanqieClosePicker();
          });
        });
        this._fanqiePickerDocumentHandlersBound = true;
      }
    },
  };
})();
(function () {
  window.NovelFanqieTaskMethods = {
    bindAutoPublishPage() {
      this.bindBookProfileControls('ap', 'auto_publish');
      this.bindChooseSource('apChooseNovel', 'auto_publish.novelFile', 'apNovelFile', '选择小说来源', (path) => this.mapSelectedBookSource('ap', 'auto_publish', path));
      document.querySelectorAll('[data-auto-op]').forEach((button) => button.addEventListener('click', () => this.runAutoPublish(button.dataset.autoOp)));
      document.getElementById('apStop')?.addEventListener('click', () => this.stopTask('auto_publish_stop', 'auto_publish'));
      document.getElementById('apPause')?.addEventListener('click', () => this.stopTask('auto_publish_pause', 'auto_publish'));
      document.getElementById('apResume')?.addEventListener('click', () => this.stopTask('auto_publish_resume', 'auto_publish'));
      this.bindManualScheduleToggle('ap');
    },
    async runAutoPublish(operation) {
      const payload = this.collectPublishPayload('ap', operation);
      if (!this.validateBookProfilePayload(payload, 'auto_publish')) return;
      this.state.config.auto_publish = payload;
      await this.saveConfig();
      if (!await this.requireFanqieLogin()) return;
      this.beginTaskUi('auto_publish', '准备启动番茄发布...');
      const ok = await this.api.auto_publish_run(payload);
      if (!ok) this.toast('任务没有启动，请查看日志。', 'warning', 'auto_publish');
    },

    bindChapterSyncPage() {
      this.bindBookProfileControls('sy', 'chapter_sync');
      this.bindChooseSource('syChooseNovel', 'chapter_sync.novelFile', 'syNovelFile', '选择小说来源', (path) => this.mapSelectedBookSource('sy', 'chapter_sync', path));
      document.querySelectorAll('[data-sync-op]').forEach((button) => button.addEventListener('click', () => this.runChapterSync(button.dataset.syncOp)));
      document.getElementById('syStop')?.addEventListener('click', () => this.stopTask('chapter_sync_stop', 'chapter_sync'));
      document.getElementById('syPause')?.addEventListener('click', () => this.stopTask('chapter_sync_pause', 'chapter_sync'));
      document.getElementById('syResume')?.addEventListener('click', () => this.stopTask('chapter_sync_resume', 'chapter_sync'));
      document.getElementById('syPullStop')?.addEventListener('click', () => this.stopTask('chapter_sync_stop', 'chapter_sync'));
      document.getElementById('syPullPause')?.addEventListener('click', () => this.stopTask('chapter_sync_pause', 'chapter_sync'));
      document.getElementById('syPullResume')?.addEventListener('click', () => this.stopTask('chapter_sync_resume', 'chapter_sync'));
      this.bindManualScheduleToggle('sy');
    },
    async runChapterSync(operation) {
      const payload = this.collectPublishPayload('sy', operation);
      if (!this.validateBookProfilePayload(payload, 'chapter_sync')) return;
      if (!this.validateSyncConcurrency(payload.syncConcurrency)) return;
      this.state.config.chapter_sync = payload;
      await this.saveConfig();
      if (!await this.requireFanqieLogin()) return;
      this.beginTaskUi('chapter_sync', '准备启动番茄同步...');
      const ok = await this.api.chapter_sync_run(payload);
      if (!ok) this.toast('任务没有启动，请查看日志。', 'warning', 'chapter_sync');
    },
    validateSyncConcurrency(value) {
      const concurrency = Number(value);
      if (Number.isInteger(concurrency) && concurrency >= 1 && concurrency <= 6) return true;
      const input = document.getElementById('sySyncConcurrency');
      this.toast('并发线程只能填写 1–6；如果要同步第 30 章，请把 30 填到“指定章节”。', 'warning', 'chapter_sync');
      this.setHeaderStatus('请检查并发线程', 'error');
      input?.focus();
      input?.select();
      return false;
    },
    bindManualScheduleToggle(prefix) {
      const checkbox = document.getElementById(`${prefix}ManualSchedule`);
      const fields = document.getElementById(`${prefix}ManualScheduleFields`);
      const sync = () => fields?.classList.toggle('hidden', !checkbox?.checked);
      checkbox?.addEventListener('change', sync);
      sync();
    },
    async requireFanqieLogin() {
      const loggedIn = !!(this.api.check_login_state && await this.api.check_login_state());
      if (loggedIn) return true;
      document.getElementById('loginModal')?.classList.add('open');
      this.setHeaderStatus('请先登录番茄账号', 'error');
      return false;
    },
    bindChooseSource(buttonId, configPath, inputId, emptyText, afterChoose) {
      const button = document.getElementById(buttonId);
      const picker = button?.closest('.file-picker');
      if (!button || !picker) return;

      this.bindFanqiePickerMenu(button, picker, [
        {
          value: 'file',
          title: '选择小说文件',
        },
        {
          value: 'folder',
          title: '选择章节文件夹',
        },
      ], async (kind) => {
        let path = '';
        if (kind === 'folder') {
          path = await this.api.choose_folder(configPath);
        } else if (kind === 'file') {
          path = await this.api.choose_file(configPath, false, '');
        }
        if (!path) return;
        this.setConfigValue(configPath, path);
        this.updateFilePicker(inputId, path, emptyText);
        if (afterChoose) await afterChoose(path);
        await this.persistPageConfig(this.currentPage);
      });
    },
    collectPublishPayload(prefix, operation) {
      const payload = {
        bookProfileId: document.getElementById(`${prefix}BookProfile`)?.value || '',
        expectedBookName: document.getElementById(`${prefix}BookName`)?.value.trim() || '',
        novelFile: document.getElementById(`${prefix}NovelFile`)?.value || '',
        chapterManageUrl: document.getElementById(`${prefix}Url`)?.dataset.actualValue || document.getElementById(`${prefix}Url`)?.value || '',
        authStatePath: '',
        start: Number(document.getElementById(`${prefix}Start`)?.value || 1),
        end: Number(document.getElementById(`${prefix}End`)?.value || 1),
        useAi: !!document.getElementById(`${prefix}UseAi`)?.checked,
        verifyAfterPublish: !!document.getElementById(`${prefix}VerifyAfterPublish`)?.checked,
        debugScreenshots: !!document.getElementById(`${prefix}DebugScreenshots`)?.checked,
        failureScreenshots: !!document.getElementById(`${prefix}FailureScreenshots`)?.checked,
        browserHeadless: !!document.getElementById(`${prefix}BrowserHeadless`)?.checked,
        clearAuthorNote: !!document.getElementById(`${prefix}ClearAuthorNote`)?.checked,
        gitTracking: !!document.getElementById(`${prefix}GitTracking`)?.checked,
        manualSchedule: !!document.getElementById(`${prefix}ManualSchedule`)?.checked,
        scheduleStartDate: document.getElementById(`${prefix}ScheduleStartDate`)?.value || '',
        scheduleMorningTime: document.getElementById(`${prefix}ScheduleMorningTime`)?.value || '10:00',
        scheduleMorningCount: Number(document.getElementById(`${prefix}ScheduleMorningCount`)?.value || 1),
        scheduleAfternoonTime: document.getElementById(`${prefix}ScheduleAfternoonTime`)?.value || '18:00',
        scheduleAfternoonCount: Number(document.getElementById(`${prefix}ScheduleAfternoonCount`)?.value || 0),
        operation,
      };
      if (prefix === 'sy') {
        payload.chapterSelection = document.getElementById('syChapterSelection')?.value || '';
        payload.syncConcurrency = Number(document.getElementById('sySyncConcurrency')?.value || 2);
      }
      return payload;
    },
  };
})();
