// YouTube ve Google cookie'lerini Netscape formatında al
async function getYouTubeCookies() {
  const domains = ["https://www.youtube.com", "https://www.google.com"];
  const seen = new Set();
  const lines = ["# Netscape HTTP Cookie File"];

  for (const domain of domains) {
    try {
      const cookies = await chrome.cookies.getAll({ url: domain });
      for (const c of cookies) {
        const key = `${c.domain}\t${c.name}`;
        if (seen.has(key)) continue;
        seen.add(key);
        const domainStr = c.domain.startsWith(".") ? c.domain : "." + c.domain;
        const path = c.path || "/";
        const secure = c.secure ? "TRUE" : "FALSE";
        const expires = c.expirationDate ? Math.floor(c.expirationDate) : 0;
        lines.push(`${domainStr}\tTRUE\t${path}\t${secure}\t${expires}\t${c.name}\t${c.value}`);
      }
    } catch (_) {}
  }

  return lines.join("\n");
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "NOUSCRIPT_GET_COOKIES") {
    getYouTubeCookies().then(sendResponse).catch(() => sendResponse(""));
    return true; // async response
  }
});
