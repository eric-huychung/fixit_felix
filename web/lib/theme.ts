/**
 * Theme handling for the local UI: one class on <html>, set before first paint.
 */

export const THEME_STORAGE_KEY = "felix-theme";

export const DARK_CLASS = "dark";

/**
 * Chooses the theme and stamps the class on <html> before the page paints.
 *
 * Rendered as a blocking script from the server-only root layout. Deciding the
 * theme here rather than in a component is what keeps every React component's
 * markup identical on the server and the client: nothing renders differently
 * per theme, so there is no hydration mismatch and no flash of the wrong theme.
 */
export const THEME_BOOTSTRAP = `(function(){try{
var s=localStorage.getItem(${JSON.stringify(THEME_STORAGE_KEY)});
var d=s?s==="dark":matchMedia("(prefers-color-scheme: dark)").matches;
document.documentElement.classList.toggle(${JSON.stringify(DARK_CLASS)},d);
}catch(e){}})();`;

/**
 * Flips the theme and remembers the choice.
 *
 * @returns True when the page is now in dark mode
 */
export function toggle_theme(): boolean {
  const is_dark = document.documentElement.classList.toggle(DARK_CLASS);
  try {
    localStorage.setItem(THEME_STORAGE_KEY, is_dark ? "dark" : "light");
  } catch {
    // Private-mode or blocked storage: the theme still flips for this page view.
  }
  return is_dark;
}
