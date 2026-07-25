const BASE_URL_PATH = import.meta.env.BASE_URL || '/'
const BASE_PATH = BASE_URL_PATH.endsWith('/') && BASE_URL_PATH !== '/' ? BASE_URL_PATH.slice(0, -1) : BASE_URL_PATH

function normalizePath(path) {
  if (!path) {
    return '/'
  }

  let normalized = path

  if (BASE_PATH !== '/' && normalized.startsWith(BASE_PATH)) {
    normalized = normalized.slice(BASE_PATH.length) || '/'
  }

  if (!normalized.startsWith('/')) {
    normalized = `/${normalized}`
  }

  return normalized === '' ? '/' : normalized
}

export function getCurrentPath() {
  const { hash, pathname } = window.location

  if (hash.startsWith('#/')) {
    return normalizePath(hash.slice(1))
  }

  return normalizePath(pathname)
}

export function buildAppHref(path) {
  const normalized = normalizePath(path)
  return `${BASE_URL_PATH}#${normalized}`
}
