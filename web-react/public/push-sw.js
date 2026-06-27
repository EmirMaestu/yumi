/* Handlers de notificaciones push. Lo importa el service worker generado por
   vite-plugin-pwa (workbox.importScripts). No tocar el precache. */
self.addEventListener('push', (event) => {
  let data = {}
  try { data = event.data ? event.data.json() : {} } catch (e) { data = { body: (event.data && event.data.text()) || '' } }
  const title = data.title || 'Yumi'
  const options = {
    body: data.body || '',
    icon: '/app/pwa-192x192.png',
    badge: '/app/pwa-192x192.png',
    tag: data.tag || undefined,
    data: { url: data.url || '/app/' },
  }
  event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = (event.notification.data && event.notification.data.url) || '/app/'
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
      for (const c of list) {
        if ('focus' in c) { try { c.navigate(url) } catch (e) {} return c.focus() }
      }
      if (self.clients.openWindow) return self.clients.openWindow(url)
    })
  )
})
