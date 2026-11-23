"""Browser request and navigation boundaries for application pages."""
import urllib.parse


NAVIGATION_GUARD = r'''(() => {
  const executable = value => {
    try { return new URL(value, document.baseURI).protocol === "javascript:"; }
    catch (_) { return true; }
  };
  const guard = event => {
    const element = event.target instanceof Element ? event.target : event.target?.parentElement;
    const link = element?.closest("a[href],area[href],form[action],[formaction]");
    if (!link) return;
    for (const attribute of ["href", "action", "formaction"]) {
      const value = link.getAttribute(attribute);
      if (value !== null && executable(value)) event.preventDefault();
    }
  };
  for (const event of ["click", "auxclick", "submit"]) document.addEventListener(event, guard, true);
  document.addEventListener("keydown", event => {
    if (event.key === "Enter" || event.key === " ") guard(event);
  }, true);
  document.addEventListener("drop", event => {
    const value = event.dataTransfer?.getData("text/uri-list") || event.dataTransfer?.getData("text/plain");
    if (value && executable(value)) event.preventDefault();
  }, true);
})();'''


async def restrict_script_request(route, origin, api_path, page_path):
    """Keep script reads within public interfaces, including their final redirect target.

    Ordinary script/style/font loading still uses the browser resource channel.
    Product HTML fragments used by UI controls are public page interfaces.
    """
    if route.request.resource_type not in {'fetch', 'xhr'}:
        return False

    def validate(url):
        target = urllib.parse.urlsplit(url)
        expected = urllib.parse.urlsplit(origin)
        if (target.scheme, target.hostname, target.port) != (expected.scheme, expected.hostname, expected.port):
            raise ValueError('Script requests must stay within the application')
        path = urllib.parse.urlunsplit(('', '', target.path, target.query, ''))
        try:
            api_path(path)
        except ValueError:
            page_path(path)

    try:
        validate(route.request.url)
        response = await route.fetch(max_redirects=10)
        validate(response.url)
    except ValueError:
        await route.abort()
    else:
        await route.fulfill(response=response)
    return True
