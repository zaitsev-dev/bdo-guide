(() => {
  const container = document.querySelector("[data-guide-video]");
  if (!container || container.__bdoGuideVideoController) return;

  const playerElement = container.querySelector("#guide-video-player");
  const videoId = container.dataset.videoId;
  if (!playerElement || !videoId) return;

  container.__bdoGuideVideoController = true;

  const apiUrl = "https://www.youtube.com/iframe_api";
  let player = null;
  let playerReady = false;
  let pendingSeconds = null;

  const playAt = (seconds) => {
    if (!playerReady || !player) {
      pendingSeconds = seconds;
      return;
    }

    player.seekTo(seconds, true);
    player.playVideo();
  };

  const onPlayerReady = (event) => {
    player = event?.target || player;
    playerReady = true;

    if (pendingSeconds === null) return;
    const seconds = pendingSeconds;
    pendingSeconds = null;
    playAt(seconds);
  };

  const createPlayer = () => {
    if (player || typeof window.YT?.Player !== "function") return;

    player = new window.YT.Player(playerElement, {
      videoId,
      playerVars: {
        playsinline: 1,
        rel: 0,
        origin: window.location.origin,
      },
      events: {
        onReady: onPlayerReady,
      },
    });
  };

  document.addEventListener("bdo-guide:seek-video", (event) => {
    const seconds = event.detail?.seconds;
    if (typeof seconds !== "number" || !Number.isFinite(seconds) || seconds < 0) return;
    playAt(seconds);
  });

  if (typeof window.YT?.Player === "function") {
    createPlayer();
    return;
  }

  const previousReadyHandler = window.onYouTubeIframeAPIReady;
  window.onYouTubeIframeAPIReady = function (...args) {
    try {
      if (typeof previousReadyHandler === "function") {
        previousReadyHandler.apply(this, args);
      }
    } finally {
      createPlayer();
    }
  };

  const apiAlreadyRequested = Array.from(document.scripts).some((script) => {
    try {
      return new URL(script.src, document.baseURI).href === apiUrl;
    } catch {
      return false;
    }
  });

  if (!apiAlreadyRequested) {
    const script = document.createElement("script");
    script.src = apiUrl;
    script.async = true;
    document.head.append(script);
  }
})();
