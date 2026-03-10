// NouScript sayfasından gelen cookie isteğini dinle
window.addEventListener("message", (event) => {
  if (event.data?.type !== "NOUSCRIPT_REQUEST_COOKIES") return;
  // Sadece aynı origin'den gelen mesajlara yanıt ver (güvenlik)
  if (event.source !== window) return;

  chrome.runtime.sendMessage({ type: "NOUSCRIPT_GET_COOKIES" }, (cookies) => {
    window.postMessage(
      { type: "NOUSCRIPT_COOKIES_RESPONSE", cookies: cookies || "" },
      "*"
    );
  });
});
