const BASE_URL = import.meta.env.BASE_URL || '/'
const BASE_PATH = BASE_URL.endsWith('/') && BASE_URL !== '/' ? BASE_URL.slice(0, -1) : BASE_URL

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
  return `${BASE_URL}#${normalized}`
}
