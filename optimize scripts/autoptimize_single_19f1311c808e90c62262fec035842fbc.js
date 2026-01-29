(function(){
  const baseUrl = document.currentScript
    ? new URL(document.currentScript.src, window.location.href)
    : new URL(window.location.href);
  const dataUrl = new URL('data/econ-strategies.json', baseUrl);

  fetch(dataUrl)
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Failed to load econ strategies data: ${response.status}`);
      }
      return response.json();
    })
    .then((data) => {
      window.econStrategiesData = data;
      document.dispatchEvent(new Event('econStrategiesDataLoaded'));
    })
    .catch((error) => {
      console.error(error);
    });
})();
