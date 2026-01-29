(function(){
  const baseUrl = document.currentScript
    ? new URL(document.currentScript.src, window.location.href)
    : new URL(window.location.href);
  const dataUrl = new URL('data/custom-condition-tooltips.json', baseUrl);

  fetch(dataUrl)
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Failed to load custom condition tooltips: ${response.status}`);
      }
      return response.json();
    })
    .then((data) => {
      window.customConditionTooltipGlobal = data;
      document.dispatchEvent(new Event('customConditionTooltipDataLoaded'));
    })
    .catch((error) => {
      console.error(error);
    });
})();
