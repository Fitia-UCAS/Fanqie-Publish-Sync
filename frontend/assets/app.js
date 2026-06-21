(function () {
  const { pageTitles, defaultPage } = window.NovelConstants;

  const app = {
    state: { config: {}, paths: {}, platforms: {} },
    currentPage: defaultPage,
    hasUserSelectedPage: false,
    api: null,
    logs: {
      auto_publish: [],
      chapter_sync: [],
    },
    logAliases: {},
    lastOutputs: {},
    lastBackups: {},
    taskStatus: {},
    progressState: {},
    taskStore: window.NovelTaskStateStore ? window.NovelTaskStateStore.create() : null,
    activeResultModes: {},
    resultTexts: {},
    saveTimer: null,
    statusOnlyPages: [],
    loglessPages: [],

    isStatusOnlyPage(page) { const targetPage = this.logAliases[page] || page; return this.statusOnlyPages.includes(targetPage); },
    isLoglessPage(page) { const targetPage = this.logAliases[page] || page; return this.loglessPages.includes(targetPage); },
    setHeaderStatus(message, level = 'ready') {
      const badge = document.getElementById('statusBadge');
      if (!badge) return;
      const text = String(message || '就绪').trim() || '就绪';
      badge.className = `status-badge ${level === 'busy' ? 'busy' : level === 'error' ? 'error' : ''}`.trim();
      badge.innerHTML = `<i></i> ${this.escape(text)}`;
    },
    ...window.NovelUiMethods,
    ...window.NovelTaskPanelMethods,
    ...window.NovelFanqieAccountMethods,
    ...window.NovelFanqieTaskMethods,
    setConfigValue(path, value) {
      if (!path) return;
      const parts = String(path).split('.').filter(Boolean);
      let cursor = this.state.config;
      parts.slice(0, -1).forEach((part) => {
        if (!cursor[part] || typeof cursor[part] !== 'object') cursor[part] = {};
        cursor = cursor[part];
      });
      if (parts.length) cursor[parts[parts.length - 1]] = value;
    },
    debounceSavePage(page) {
      window.clearTimeout(this.saveTimer);
      this.saveTimer = window.setTimeout(() => this.persistPageConfig(page), 350);
    },
    async persistPageConfig(page) {
      try {
        if (page === 'auto_publish') {
          this.state.config.auto_publish = this.collectPublishPayload('ap', this.state.config.auto_publish?.operation || 'publish');
        } else if (page === 'chapter_sync') {
          this.state.config.chapter_sync = this.collectPublishPayload('sy', this.state.config.chapter_sync?.operation || 'publish');
        }
        this.state.config.activePage = this.currentPage;
        await this.api.save_config(this.state.config);
      } catch (error) {
        console.debug('save config failed', error);
      }
    },
    bindFormAutosave(page) {
      const root = document.querySelector(`[data-page="${page}"] .fanqie-settings-card`);
      if (!root) return;
      const handler = () => this.debounceSavePage(page);
      root.addEventListener('input', handler);
      root.addEventListener('change', handler);
    },
    async init() {
      await this.waitForApi();
      this.state = await this.api.get_state();
      this.currentPage = pageTitles[this.state.config.activePage] ? this.state.config.activePage : defaultPage;
      this.bindShell();
      this.render();
      await this.refreshLoginState();
    },
    waitForApi() {
      return new Promise((resolve) => {
        const ready = () => {
          this.api = window.pywebview && window.pywebview.api;
          if (this.api) resolve();
        };
        if (window.pywebview && window.pywebview.api) return ready();
        window.addEventListener('pywebviewready', ready, { once: true });
      });
    },
    bindShell() {
      const brandButton = document.getElementById('brandButton');
      const pageMenu = document.getElementById('pageMenu');
      const switchPage = (event) => {
        const button = event.target.closest('[data-page]');
        if (!button) return;
        pageMenu?.classList.remove('open');
        brandButton?.setAttribute('aria-expanded', 'false');
        this.hasUserSelectedPage = true;
        this.go(button.dataset.page);
      };
      brandButton?.addEventListener('click', (event) => {
        event.stopPropagation();
        const isOpen = pageMenu?.classList.toggle('open');
        brandButton.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      });
      pageMenu?.addEventListener('click', switchPage);
      document.addEventListener('click', () => {
        pageMenu?.classList.remove('open');
        brandButton?.setAttribute('aria-expanded', 'false');
      });
      this.bindLoginControls();
      document.getElementById('resetDataButton')?.addEventListener('click', async () => {
        if (!this.api.reset_app_data) return;
        this.setHeaderStatus('正在重置数据...', 'busy');
        try {
          const result = await this.api.reset_app_data();
          this.state = await this.api.get_state();
          this.currentPage = pageTitles[this.state.config.activePage] ? this.state.config.activePage : defaultPage;
          this.logs = {
            auto_publish: [],
            chapter_sync: [],
          };
          this.lastOutputs = {};
          this.lastBackups = {};
          this.taskStatus = {};
          this.progressState = {};
          this.taskStore = window.NovelTaskStateStore ? window.NovelTaskStateStore.create() : null;
          this.activeResultModes = {};
          this.resultTexts = {};
          this.render();
          this.setHeaderStatus(result && result.ok ? '数据已重建' : '重建失败', result && result.ok ? 'ready' : 'error');
        } catch (error) {
          console.debug('reset data failed', error);
          this.setHeaderStatus('重建失败', 'error');
        }
      });
      this.bindThemeControls();
      document.body.addEventListener('click', async (event) => {
        const copy = event.target.closest('[data-copy-output]');
        if (copy) this.copyOutput(copy.dataset.copyOutput);
        const clear = event.target.closest('[data-clear-output]');
        if (clear) this.clearOutput(clear.dataset.clearOutput);
        const openOutput = event.target.closest('[data-open-output]');
        if (openOutput) await this.openOutputDir(openOutput.dataset.openOutput);
        const openLog = event.target.closest('[data-open-log]');
        if (openLog) await this.openTaskLog(openLog.dataset.openLog);
        const openBackup = event.target.closest('[data-open-backup]');
        if (openBackup) await this.openBackup(openBackup.dataset.openBackup);
      });
    },
    bindThemeControls() {
      const modal = document.getElementById('themeModal');
      document.getElementById('themeButton')?.addEventListener('click', () => modal?.classList.add('open'));
      document.getElementById('themeClose')?.addEventListener('click', () => modal?.classList.remove('open'));
      modal?.addEventListener('click', (event) => {
        if (event.target === modal) modal.classList.remove('open');
      });
      document.querySelectorAll('[data-theme]').forEach((button) => button.addEventListener('click', () => {
        const theme = button.dataset.theme || 'blue';
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
      }));
      document.documentElement.setAttribute('data-theme', localStorage.getItem('theme') || 'blue');
    },
    bindLoginControls() {
      const modal = document.getElementById('loginModal');
      const close = () => modal?.classList.remove('open');
      document.getElementById('loginButton')?.addEventListener('click', async () => {
        modal?.classList.add('open');
        await this.refreshLoginState();
      });
      document.getElementById('loginClose')?.addEventListener('click', close);
      modal?.addEventListener('click', (event) => {
        if (event.target === modal) close();
      });
      document.getElementById('loginStart')?.addEventListener('click', async () => {
        close();
        this.setHeaderStatus('正在打开登录页面', 'busy');
        try {
          const result = await this.api.do_login();
          await this.refreshLoginState();
          this.setHeaderStatus(
            result && result.ok ? '账号已登录' : (result && result.message ? result.message : '登录未完成'),
            result && result.ok ? 'ready' : 'error',
          );
        } catch (error) {
          this.setHeaderStatus(`登录页面打开失败：${error && error.message ? error.message : error}`, 'error');
        }
      });
      document.getElementById('loginImport')?.addEventListener('click', async () => {
        this.setLoginControlsBusy(true, '正在导入登录状态');
        const result = await this.api.import_login_state();
        this.setLoginControlsBusy(false);
        await this.refreshLoginState();
        if (result && result.message) this.setHeaderStatus(result.message, result.ok ? 'ready' : 'error');
      });
      document.getElementById('loginReset')?.addEventListener('click', async () => {
        this.setLoginControlsBusy(true, '正在清除登录状态');
        const result = await this.api.reset_login();
        this.setLoginControlsBusy(false);
        await this.refreshLoginState();
        this.setHeaderStatus(result && result.ok ? '登录状态已清除' : '清除失败', result && result.ok ? 'ready' : 'error');
      });
    },
    setLoginControlsBusy(busy, message = '') {
      ['loginStart', 'loginImport', 'loginReset'].forEach((id) => {
        const button = document.getElementById(id);
        if (button) button.disabled = !!busy;
      });
      if (message) {
        const text = document.getElementById('loginStateText');
        if (text) text.textContent = message;
      }
    },
    async refreshLoginState() {
      if (!this.api || !this.api.check_login_state) return false;
      const loggedIn = await this.api.check_login_state();
      const button = document.getElementById('loginButton');
      if (button) button.textContent = loggedIn ? '账号已登录' : '账号登录';
      return !!loggedIn;
    },
    async saveConfig() {
      this.state.config.activePage = this.currentPage;
      await this.api.save_config(this.state.config);
    },
    async go(page) {
      this.currentPage = pageTitles[page] ? page : defaultPage;
      this.render();
      await this.saveConfig();
    },
    render() {
      const [, title] = pageTitles[this.currentPage] || pageTitles[defaultPage];
      document.title = this.hasUserSelectedPage ? `${title} - 番茄发布同步助手` : '番茄发布同步助手';
      const brandModeText = document.getElementById('brandModeText');
      if (brandModeText) brandModeText.textContent = this.hasUserSelectedPage ? title : 'LOCAL TOOL';
      document.querySelectorAll('#pageMenu [data-page]').forEach((button) => button.classList.toggle('active', button.dataset.page === this.currentPage));
      const renderer = {
        auto_publish: window.renderFanqiePublisherPage,
        chapter_sync: window.renderFanqieSyncerPage,
      }[this.currentPage] || window.renderFanqiePublisherPage;
      document.getElementById('pageHost').innerHTML = renderer(this);
      this.bindPage(this.currentPage);
      this.restorePageLogs();
    },
    restorePageLogs() {
      this.restoreLog(this.currentPage);
    },
    bindPage(page) {
      if (page === 'auto_publish') this.bindAutoPublishPage();
      if (page === 'chapter_sync') this.bindChapterSyncPage();
      this.bindFormAutosave(page);
    },

    async stopTask(apiName, page) {
      if (!this.api[apiName]) return this.toast('当前版本不支持停止任务。', 'warning', page);
      const ok = await this.api[apiName]();
      if (!ok) this.toast('当前没有正在运行的任务。', 'warning', page);
    },

    bindChooseFile(buttonId, configPath, inputId, emptyText, afterChoose, save = false, suggestedName = '') {
      document.getElementById(buttonId)?.addEventListener('click', async () => {
        const filename = typeof suggestedName === 'function' ? suggestedName() : suggestedName;
        const path = await this.api.choose_file(configPath, save, filename || 'output.txt');
        if (!path) return;
        this.setConfigValue(configPath, path);
        this.updateFilePicker(inputId, path, emptyText);
        if (afterChoose) await afterChoose(path);
        await this.persistPageConfig(this.currentPage);
      });
    },
    bindChooseFolder(buttonId, configPath, inputId, emptyText, afterChoose) {
      document.getElementById(buttonId)?.addEventListener('click', async () => {
        const path = await this.api.choose_folder(configPath);
        if (!path) return;
        this.setConfigValue(configPath, path);
        this.updateFilePicker(inputId, path, emptyText);
        if (afterChoose) await afterChoose(path);
        await this.persistPageConfig(this.currentPage);
      });
    },

  };

  window.NovelTools = app;
  app.init().catch((error) => {
    console.error(error);
    document.getElementById('pageHost').innerHTML = `<div class="card"><h2>启动失败</h2><p>${String(error)}</p></div>`;
  });
})();
