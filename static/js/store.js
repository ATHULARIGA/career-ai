/**
 * Lightweight reactive state store for ResuMate frontend modules.
 */
(function (global) {
  function createStore(initialState) {
    let state = Object.assign({}, initialState || {});
    const listeners = new Set();

    return {
      getState() {
        return state;
      },
      setState(patch) {
        const next = typeof patch === 'function' ? patch(state) : patch;
        state = Object.assign({}, state, next || {});
        listeners.forEach((fn) => {
          try {
            fn(state);
          } catch (_) {
            // Isolate listener errors
          }
        });
        return state;
      },
      subscribe(fn) {
        listeners.add(fn);
        return () => listeners.delete(fn);
      },
    };
  }

  global.ResuMateStore = { createStore };
})(window);
