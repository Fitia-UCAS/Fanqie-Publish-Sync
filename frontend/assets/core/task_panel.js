(function () {
  window.NovelTaskPanelMethods = {
    renderTerminalPanel(page) {
      const statusOnly = this.isStatusOnlyPage(page);
      const logless = this.isLoglessPage(page);
      const actions = `<button class="terminal-clear" data-clear-output="${this.attr(page)}" type="button">清空</button>
            <button class="terminal-copy" data-copy-output="${this.attr(page)}" type="button">复制</button>
            <button class="terminal-open-log" data-open-log="${this.attr(page)}" type="button">打开日志</button>
            <button class="terminal-open-backup" data-open-backup="${this.attr(page)}" type="button">打开备份</button>
            <button class="terminal-open" data-open-output="${this.attr(page)}" type="button">打开目录</button>`;
      return `<div class="terminal-card ${statusOnly ? 'status-panel' : ''} ${logless ? 'logless-panel' : ''}">
        <div class="terminal-head">
          <div class="terminal-dots"><i></i><i></i><i></i></div>
          <b>运行日志</b>
          <div class="terminal-actions">
            ${actions}
          </div>
        </div>
        <div class="terminal-progress" id="${this.attr(page)}ProgressWrap">
          <span id="${this.attr(page)}ProgressText">0/0</span>
          <div class="progress" id="${this.attr(page)}ProgressTrack"><i id="${this.attr(page)}ProgressBar"></i></div>
          <span id="${this.attr(page)}ProgressPercent">0%</span>
        </div>
        ${logless ? '' : `<div class="terminal-log" id="${this.attr(page)}Log"></div>`}
      </div>`;
    },

    statePath(key) {
      return (this.state && this.state.paths && this.state.paths[key]) || key;
    },
    outputPathForPage(page) {
      const featureRootPages = {
        auto_publish: 'fanqie_publisher',
        chapter_sync: 'fanqie_syncer',
      };
      if (featureRootPages[page]) return this.statePath(featureRootPages[page]);
      return this.lastOutputs[page] || this.statePath('data');
    },
    async openOutputDir(page) {
      const path = this.outputPathForPage(page);
      if (!path || !this.api.open_path) return this.toast('没有可打开的输出目录。', 'warning', page);
      const ok = await this.api.open_path(path);
      if (!ok) this.toast('打开输出目录失败。', 'error', page);
    },
    async openTaskLog(page) {
      if (!this.api.open_log) return this.toast('当前版本不支持直接打开日志。', 'warning', page);
      const ok = await this.api.open_log(page);
      if (!ok) this.toast('打开日志失败。', 'error', page);
    },
    async openBackup(page) {
      const path = this.lastBackups[page] || '';
      if (!path || !this.api.open_backup) return this.toast('当前任务暂无可打开的备份。', 'warning', page);
      const ok = await this.api.open_backup(path);
      if (!ok) this.toast('打开备份失败。', 'error', page);
    },

    beginTaskUi(page, message) {
      const targetPage = this.logAliases[page] || page;
      this.logs[targetPage] = [];
      if (this.resultTexts) this.resultTexts[targetPage] = '';
      this.progressState[targetPage] = { current: 0, total: 1 };
      if (this.taskStore) this.taskStore.begin(targetPage, message || '任务启动中...');
      this.setProgress(targetPage, 0, 1);
      this.setTaskStatus(targetPage, message || '任务启动中...', 'info');
      this.setTaskSummary(targetPage, '暂无', 'info');
      const box = document.getElementById(`${targetPage}Log`);
      if (box) {
        box.innerHTML = '';
        box.classList.toggle('result-text', this.activeResultModes?.[targetPage] === 'chapter_text');
      }
    },
    setTaskStatus(page, message, level = 'info') {
      const targetPage = this.logAliases[page] || page;
      const text = String(message || '').trim();
      if (!text) return;
      this.taskStatus[targetPage] = { message: text, level };
      this.renderTaskMetrics(targetPage);
      if (targetPage === this.currentPage) {
        const headerLevel = level === 'error' ? 'error' : (level === 'success' ? 'ready' : 'busy');
        const headerText = level === 'error' ? '任务失败' : (level === 'success' ? '任务完成' : '任务运行中');
        this.setHeaderStatus(headerText, headerLevel);
      }
    },
    setTaskSummary(page, summary, level = 'info') {
    },
    conciseTaskMessage(message, page = '') {
      const text = String(message || '').trim();
      if (!text) return '';
      return text;
    },

    async copyOutput(page) {
      const resultText = String(this.resultTexts?.[page] || '').trim();
      const logText = (document.getElementById(`${page}Log`)?.innerText || '').trim();
      const text = resultText || logText;
      if (!text) return this.toast('暂无可复制内容。', 'warning', page);
      try {
        await navigator.clipboard.writeText(text);
        this.toast('已复制。', 'success', page);
      } catch (_) {
        const area = document.createElement('textarea');
        area.value = text;
        area.style.position = 'fixed';
        area.style.left = '-9999px';
        document.body.appendChild(area);
        area.select();
        document.execCommand('copy');
        area.remove();
        this.toast('已复制。', 'success', page);
      }
    },
    applyTaskEvent(event) {
      const page = event && event.page ? event.page : this.currentPage;
      const targetPage = this.logAliases[page] || page;
      const state = this.taskStore ? this.taskStore.applyEvent(event || {}) : null;
      const progress = event && event.payload && event.payload.progress;
      if (progress) this.setProgress(targetPage, progress.current, progress.total);
      this.renderTaskMetrics(targetPage, state);
      if (event && event.eventType === 'progress') return;
      const text = event && typeof event.displayMessage === 'string'
        ? event.displayMessage
        : (event && typeof event.message === 'string' ? event.message : '');
      this.appendLog(targetPage, text, event && event.level || 'info', event || {});
    },
    renderTaskMetrics(page, state = null) {
      const targetPage = this.logAliases[page] || page;
      if (state && this.taskStore) this.taskStore.states[targetPage] = state;
    },
    shouldUpdateTaskStatus(message, level, event = {}) {
      if (level === 'error' || level === 'warn' || level === 'warning') return true;
      if (['stage', 'completed', 'stopped', 'failed', 'error'].includes(String(event.eventType || ''))) return true;
      const text = String(message || '');
      return /^第\s*\d+\s*章（\d+\/\d+）：处理中/.test(text) || text.startsWith('正在最终校验');
    },
    logItemTime(event = {}) {
      const value = event.timestamp ? new Date(event.timestamp) : new Date();
      if (Number.isNaN(value.getTime())) return new Date().toLocaleTimeString([], { hour12: false });
      return value.toLocaleTimeString([], { hour12: false });
    },
    createLogLine(item) {
      const line = document.createElement('div');
      line.className = `log-line ${item.level}`;
      const time = document.createElement('time');
      time.textContent = item.time;
      const message = document.createElement('span');
      message.className = 'log-message';
      message.textContent = item.message;
      const repeat = document.createElement('span');
      repeat.className = 'log-repeat';
      repeat.textContent = item.count > 1 ? `×${item.count}` : '';
      line.append(time, message, repeat);
      return line;
    },
    appendLog(page, message, level = 'info', event = {}) {
      const targetPage = this.logAliases[page] || page;
      const normalizedLevel = level === 'warning' ? 'warn' : level;
      const text = this.conciseTaskMessage(message, targetPage);
      if (!text) return;
      if (this.shouldUpdateTaskStatus(text, normalizedLevel, event)) this.setTaskStatus(targetPage, text, normalizedLevel);
      if (this.isLoglessPage(targetPage)) return;
      if (!this.logs[targetPage]) this.logs[targetPage] = [];
      const item = {
        message: text,
        level: normalizedLevel,
        time: this.logItemTime(event),
        count: 1,
      };
      const last = this.logs[targetPage].slice(-1)[0];
      const box = document.getElementById(`${targetPage}Log`);
      if (last && last.message === item.message && last.level === item.level) {
        last.count = Number(last.count || 1) + 1;
        const repeat = box?.lastElementChild?.querySelector('.log-repeat');
        if (repeat) repeat.textContent = `×${last.count}`;
        return;
      }
      this.logs[targetPage].push(item);
      if (!box) return;
      box.appendChild(this.createLogLine(item));
      box.scrollTop = box.scrollHeight;
    },
    restoreLog(page) {
      const box = document.getElementById(`${page}Log`);
      const progress = this.progressState[page];
      if (progress) this.setProgress(page, progress.current, progress.total);
      this.renderTaskMetrics(page);
      if (!box) return;
      box.innerHTML = '';
      box.classList.remove('result-text');
      if (this.resultTexts?.[page]) {
        this.showResultText(page, this.resultTexts[page]);
        return;
      }
      (this.logs[page] || []).forEach((item) => {
        box.appendChild(this.createLogLine(Object.assign({ time: '', count: 1 }, item)));
      });
      if (!box.innerHTML && this.activeResultModes?.[page] === 'chapter_text') box.innerHTML = '';
      box.scrollTop = box.scrollHeight;
    },
    clearOutput(page) {
      this.logs[page] = [];
      if (this.resultTexts) this.resultTexts[page] = '';
      if (this.activeResultModes) this.activeResultModes[page] = '';
      this.progressState[page] = { current: 0, total: 0 };
      if (this.taskStore) this.taskStore.begin(page, '等待执行');
      this.setProgress(page, 0, 0);
      this.setTaskStatus(page, '等待执行', 'info');
      this.setTaskSummary(page, '暂无', 'info');
      const box = document.getElementById(`${page}Log`);
      if (box) {
        box.classList.remove('result-text');
        box.innerHTML = '';
      }
    },
    showResultText(page, text) {
      const targetPage = this.logAliases[page] || page;
      const box = document.getElementById(`${targetPage}Log`);
      if (!box) return;
      box.innerHTML = '';
      box.classList.add('result-text');
      box.textContent = String(text || '');
      box.scrollTop = 0;
    },
    setProgress(page, current, total) {
      const targetPage = this.logAliases[page] || page;
      const totalValue = Math.max(0, Number(total || 0));
      const rawCurrent = Math.max(0, Number(current || 0));
      const currentValue = totalValue > 0 ? Math.min(rawCurrent, totalValue) : rawCurrent;
      const percent = totalValue > 0 ? Math.max(0, Math.min(100, Math.round((currentValue / totalValue) * 100))) : 0;
      this.progressState[targetPage] = { current: currentValue, total: totalValue };
      if (this.taskStore) this.taskStore.setProgress(targetPage, currentValue, totalValue);
      const displayTotal = totalValue > 0 ? Math.ceil(totalValue) : 0;
      const displayCurrent = totalValue > 0 ? (currentValue <= 0 ? 0 : Math.min(displayTotal, Math.ceil(currentValue))) : 0;
      const text = document.getElementById(`${targetPage}ProgressText`);
      const bar = document.getElementById(`${targetPage}ProgressBar`);
      const track = document.getElementById(`${targetPage}ProgressTrack`);
      const percentText = document.getElementById(`${targetPage}ProgressPercent`);
      if (text) text.textContent = `${displayCurrent}/${displayTotal}`;
      if (bar) bar.style.width = `${percent}%`;
      if (percentText) percentText.textContent = `${percent}%`;
      if (track) track.classList.toggle('running', percent > 0 && percent < 100);
      this.renderTaskMetrics(targetPage);
    },
    taskDone(page, ok, result) {
      const targetPage = this.logAliases[page] || page;
      const message = result && result.message ? result.message : (ok ? '任务完成' : '任务失败');
      const state = this.progressState[targetPage] || { current: 0, total: 1 };
      if (ok) this.setProgress(targetPage, state.total || 1, state.total || 1);
      if (result && result.path) this.lastOutputs[targetPage] = result.path;
      if (result && result.backupPath) this.lastBackups[targetPage] = result.backupPath;
      else if (result && result.backupDir) this.lastBackups[targetPage] = result.backupDir;
      else if (result && Array.isArray(result.backupPaths) && result.backupPaths.length) this.lastBackups[targetPage] = result.backupPaths[result.backupPaths.length - 1];

      const finalMessage = ok ? message : `${message}（详情见对应 tasklogs 目录）`;
      if (this.taskStore) this.taskStore.finish(targetPage, ok, finalMessage);
      this.setTaskStatus(targetPage, finalMessage, ok ? 'success' : 'error');
      this.setTaskSummary(targetPage, finalMessage, ok ? 'success' : 'error');

      const resultDisplayMode = result && result.resultDisplayMode ? String(result.resultDisplayMode) : '';
      const resultText = result && result.resultText ? String(result.resultText) : '';
      if (ok && resultDisplayMode === 'chapter_text') {
        this.activeResultModes[targetPage] = 'chapter_text';
        this.resultTexts[targetPage] = resultText;
        this.showResultText(targetPage, resultText);
        return;
      }

      const box = document.getElementById(`${targetPage}Log`);
      if (box) box.classList.remove('result-text');
      this.appendLog(targetPage, finalMessage, ok ? 'success' : 'error', {
        label: ok ? '完成' : '错误',
        eventType: ok ? 'completed' : 'error',
        timestamp: new Date().toISOString(),
      });
    },
    toast(message, level = 'info', page = this.currentPage) {
      const text = String(message || '').trim();
      if (!text) return;
      if (this.isLoglessPage(page) && text === '已复制。') return;
      this.appendLog(page, text, level);
    }
  };
})();

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
      this.bindChooseSource('apChooseNovel', 'auto_publish.novelFile', 'apNovelFile', '选择小说来源');
      this.bindMaskedUrl('apUrl');
      document.querySelectorAll('[data-auto-op]').forEach((button) => button.addEventListener('click', () => this.runAutoPublish(button.dataset.autoOp)));
      document.getElementById('apStop')?.addEventListener('click', () => this.stopTask('auto_publish_stop', 'auto_publish'));
      document.getElementById('apPause')?.addEventListener('click', () => this.stopTask('auto_publish_pause', 'auto_publish'));
      document.getElementById('apResume')?.addEventListener('click', () => this.stopTask('auto_publish_resume', 'auto_publish'));
      this.bindManualScheduleToggle('ap');
    },
    async runAutoPublish(operation) {
      const payload = this.collectPublishPayload('ap', operation);
      this.state.config.auto_publish = payload;
      await this.saveConfig();
      if (!await this.requireFanqieLogin()) return;
      this.beginTaskUi('auto_publish', '准备启动番茄发布...');
      const ok = await this.api.auto_publish_run(payload);
      if (!ok) this.toast('任务没有启动，请查看日志。', 'warning', 'auto_publish');
    },

    bindChapterSyncPage() {
      this.bindChooseSource('syChooseNovel', 'chapter_sync.novelFile', 'syNovelFile', '选择小说来源');
      this.bindMaskedUrl('syUrl');
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
      this.state.config.chapter_sync = payload;
      await this.saveConfig();
      if (!await this.requireFanqieLogin()) return;
      this.beginTaskUi('chapter_sync', '准备启动番茄同步...');
      const ok = await this.api.chapter_sync_run(payload);
      if (!ok) this.toast('任务没有启动，请查看日志。', 'warning', 'chapter_sync');
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
    bindMaskedUrl(inputId) {
      const input = document.getElementById(inputId);
      if (!input) return;
      const mask = '••••••••••••';
      input.dataset.actualValue = input.value || '';
      const conceal = () => {
        if (input.dataset.actualValue) input.value = mask;
      };
      input.addEventListener('focus', () => {
        input.value = input.dataset.actualValue || '';
        input.select();
      });
      input.addEventListener('input', () => {
        input.dataset.actualValue = input.value;
      });
      input.addEventListener('blur', conceal);
      conceal();
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
      return {
        novelFile: document.getElementById(`${prefix}NovelFile`)?.value || '',
        chapterManageUrl: document.getElementById(`${prefix}Url`)?.dataset.actualValue || document.getElementById(`${prefix}Url`)?.value || '',
        authStatePath: '',
        start: Number(document.getElementById(`${prefix}Start`)?.value || 1),
        end: Number(document.getElementById(`${prefix}End`)?.value || 1),
        useAi: !!document.getElementById(`${prefix}UseAi`)?.checked,
        verifyAfterPublish: !!document.getElementById(`${prefix}VerifyAfterPublish`)?.checked,
        debugScreenshots: !!document.getElementById(`${prefix}DebugScreenshots`)?.checked,
        failureScreenshots: !!document.getElementById(`${prefix}FailureScreenshots`)?.checked,
        gitTracking: !!document.getElementById(`${prefix}GitTracking`)?.checked,
        manualSchedule: !!document.getElementById(`${prefix}ManualSchedule`)?.checked,
        scheduleStartDate: document.getElementById(`${prefix}ScheduleStartDate`)?.value || '',
        scheduleMorningTime: document.getElementById(`${prefix}ScheduleMorningTime`)?.value || '10:00',
        scheduleMorningCount: Number(document.getElementById(`${prefix}ScheduleMorningCount`)?.value || 1),
        scheduleAfternoonTime: document.getElementById(`${prefix}ScheduleAfternoonTime`)?.value || '18:00',
        scheduleAfternoonCount: Number(document.getElementById(`${prefix}ScheduleAfternoonCount`)?.value || 0),
        operation,
      };
    },
  };
})();
