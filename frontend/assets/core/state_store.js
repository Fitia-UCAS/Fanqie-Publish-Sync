(function () {
  function initialState(page) {
    return {
      page,
      phase: '等待',
      status: '等待执行',
      level: 'info',
      current: 0,
      total: 0,
      percent: 0,
      fetched: 0,
      written: 0,
      failed: 0,
      limited: 0,
      retryRound: 0,
      lastEventType: 'idle',
      updatedAt: Date.now(),
    };
  }

  function progressPercent(current, total) {
    const totalValue = Math.max(0, Number(total || 0));
    const currentValue = Math.max(0, Number(current || 0));
    if (totalValue <= 0) return 0;
    return Math.max(0, Math.min(100, Math.round((currentValue / totalValue) * 100)));
  }

  function applyLabelStats(state, event) {
    const label = String(event.label || '');
    const eventType = String(event.eventType || '');
    if (label === '阶段') state.phase = event.message || '执行中';
    if (label === '补抓') state.retryRound += 1;
    if (label === '抓取' || eventType === 'chapter_fetched') state.fetched += 1;
    if (label === '写入' || eventType === 'chapter_written') state.written += 1;
    if (label === '失败' || eventType === 'failed') state.failed += 1;
    if (label === '限流' || eventType === 'rate_limited') state.limited += 1;
    if (label === '完成') state.phase = '完成';
    if (label === '停止') state.phase = '停止';
    if (label === '错误') state.phase = '错误';
  }

  window.NovelTaskStateStore = {
    create() {
      return {
        states: {},
        ensure(page) {
          const key = String(page || 'auto_publish');
          if (!this.states[key]) this.states[key] = initialState(key);
          return this.states[key];
        },
        begin(page, message) {
          const state = initialState(page);
          state.status = message || '任务启动中...';
          state.phase = '启动';
          this.states[page] = state;
          return state;
        },
        applyEvent(event) {
          const page = String(event && event.page || 'auto_publish');
          const state = this.ensure(page);
          const payload = event && event.payload || {};
          const progress = payload.progress || null;
          if (progress) this.setProgress(page, progress.current, progress.total);
          applyLabelStats(state, event || {});
          state.status = event.displayMessage || (event.label && event.message ? `${event.label}：${event.message}` : event.message) || state.status;
          state.level = event.level || state.level;
          state.lastEventType = event.eventType || state.lastEventType;
          state.updatedAt = Date.now();
          return state;
        },
        setProgress(page, current, total) {
          const state = this.ensure(page);
          state.current = Math.max(0, Number(current || 0));
          state.total = Math.max(0, Number(total || 0));
          state.percent = progressPercent(state.current, state.total);
          state.updatedAt = Date.now();
          return state;
        },
        finish(page, ok, message) {
          const state = this.ensure(page);
          state.phase = ok ? '完成' : '错误';
          state.status = message || (ok ? '任务完成' : '任务失败');
          state.level = ok ? 'success' : 'error';
          if (ok && state.total > 0) {
            state.current = state.total;
            state.percent = 100;
          }
          state.updatedAt = Date.now();
          return state;
        },
        snapshot(page) {
          return Object.assign({}, this.ensure(page));
        },
      };
    },
  };
})();
