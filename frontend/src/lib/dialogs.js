export const confirmWithFallback = (message) => {
  try {
    return {
      available: true,
      confirmed: window.confirm(message),
    };
  } catch (_error) {
    return {
      available: false,
      confirmed: false,
    };
  }
};

export const alertWithFallback = (message) => {
  try {
    window.alert(message);
    return true;
  } catch (_error) {
    return false;
  }
};

export const promptWithFallback = (message) => {
  try {
    return {
      available: true,
      value: window.prompt(message),
    };
  } catch (_error) {
    return {
      available: false,
      value: null,
    };
  }
};
