// Civic Eye - behaviour (JavaScript)
const $ = id => document.getElementById(id);
let photoData = "", coords = "";

// Data is now stored by the Flask backend (SQLite), not in the browser.

// --- tab switching ---
document.querySelectorAll("nav button").forEach(b => b.onclick = () => {
  document.querySelectorAll("nav button").forEach(x => x.classList.toggle("on", x === b));
  document.querySelectorAll(".view").forEach(v => v.classList.toggle("on", v.id === b.dataset.v));
  if(b.dataset.v === "track") renderTrack();
});

// --- photo upload: shrink the image so it fits in browser storage ---
$("photoBox").onclick = () => $("file").click();
$("photoBox").onkeydown = e => { if(e.key==="Enter"||e.key===" "){ e.preventDefault(); $("file").click(); } };
$("file").onchange = e => {
  const f = e.target.files[0]; if(!f) return;
  const reader = new FileReader();
  reader.onload = () => {
    const img = new Image();
    img.onload = () => {
      const s = Math.min(1, 640 / Math.max(img.width, img.height));
      const c = document.createElement("canvas");
      c.width = img.width * s; c.height = img.height * s;
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      photoData = c.toDataURL("image/jpeg", 0.7);
      $("preview").src = photoData; $("preview").style.display = "inline-block";
      $("photoText").textContent = "Photo added. Tap to change.";
    };
    img.src = reader.result;
  };
  reader.readAsDataURL(f);
};

// --- live camera (getUserMedia) ---
let stream = null;
$("camBtn").onclick = async () => {
  try{
    stream = await navigator.mediaDevices.getUserMedia({video:{facingMode:"environment"}});
    $("vid").srcObject = stream; $("camBox").style.display = "block";
  }catch(e){ $("err").textContent = "Camera not available or permission denied. Use the photo box to choose a file instead."; }
};
function stopCam(){ if(stream){ stream.getTracks().forEach(t => t.stop()); stream = null; } $("camBox").style.display = "none"; }
$("camClose").onclick = stopCam;
$("snap").onclick = () => {
  const v = $("vid"); if(!v.videoWidth) return;
  const s = Math.min(1, 640 / Math.max(v.videoWidth, v.videoHeight));
  const c = document.createElement("canvas"); c.width = v.videoWidth * s; c.height = v.videoHeight * s;
  c.getContext("2d").drawImage(v, 0, 0, c.width, c.height);
  photoData = c.toDataURL("image/jpeg", 0.7);
  $("preview").src = photoData; $("preview").style.display = "inline-block";
  $("photoText").textContent = "Photo captured. Tap here to choose a different file.";
  stopCam();
};

// --- GPS location ---
$("gps").onclick = () => {
  if(!navigator.geolocation){ $("gpsNote").textContent = "Your browser does not support GPS. Type the address instead."; return; }
  $("gpsNote").textContent = "Finding your location…";
  navigator.geolocation.getCurrentPosition(p => {
    coords = p.coords.latitude.toFixed(5) + ", " + p.coords.longitude.toFixed(5);
    $("addr").value = "GPS: " + coords;
    $("gpsNote").textContent = "Location captured: " + coords + ". Looking up address…";
    fetch("https://nominatim.openstreetmap.org/reverse?format=json&lat=" + p.coords.latitude + "&lon=" + p.coords.longitude)
      .then(r => r.json())
      .then(j => { if(j.display_name){ $("addr").value = j.display_name; $("gpsNote").textContent = "Address found from GPS. You can edit it."; } })
      .catch(() => { $("gpsNote").textContent = "Location captured: " + coords + " (address lookup needs internet)."; });
  }, () => { $("gpsNote").textContent = "Could not get location. Allow location access or type the address."; });
};

// --- submit: sends the report to the Flask backend ---
$("form").onsubmit = async e => {
  e.preventDefault();
  const addr=$("addr").value.trim();
  let msg = "";
  if(!photoData) msg = "Add a photo of the problem.";
  else if(!addr) msg = "Enter the location or tap Use my location.";
  $("err").textContent = msg; if(msg) return;
  try{
    const res = await fetch("/api/reports", {method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({addr, coords, photo:photoData})});
    const r = await res.json();
    if(!res.ok){ $("err").textContent = r.error || "Could not send the report."; return; }
    $("formBox").style.display = "none"; $("done").style.display = "block";
    $("doneId").textContent = r.id;
    $("doneMsg").textContent = "Your photo has been received. The admin will forward it to the concerned BMC department.";
    stats();
  }catch(err){ $("err").textContent = "Server not reachable. Make sure app.py is running."; }
};
$("again").onclick = () => {
  $("form").reset(); photoData = ""; coords = ""; $("preview").style.display = "none";
  $("photoText").textContent = "Tap to take or choose a photo"; $("gpsNote").textContent = "";
  $("done").style.display = "none"; $("formBox").style.display = "block";
};

// --- show reports (loaded from the backend) ---
function card(r){
  const d = document.createElement("div"); d.className = "item";
  const pic = r.photo ? `<img src="${r.photo}" alt="Photo for ${r.id}">` : `<div class="noimg"></div>`;
  const st = r.status === "In progress" ? "Progress" : r.status;
  d.innerHTML = pic + `<div><h3></h3><div class="meta"></div><span class="tag ${st}">${r.status}</span></div>`;
  d.querySelector("h3").textContent = r.id;
  [ "Location: " + r.addr, r.dept ? "Sent to: " + r.dept : "Waiting for the admin to assign a department", "Reported on " + r.date ]
    .forEach(t => { const p = document.createElement("div"); p.textContent = t; d.querySelector(".meta").appendChild(p); });
  return d;
}
function fill(box, list, emptyMsg){
  box.innerHTML = "";
  if(!list.length){ box.innerHTML = `<div class="empty">${emptyMsg}</div>`; return; }
  list.forEach(r => box.appendChild(card(r)));
}
async function getReports(params){
  try{ const res = await fetch("/api/reports?" + new URLSearchParams(params)); return await res.json(); }
  catch(e){ return []; }
}
async function renderTrack(){
  const q = $("q").value.trim().toUpperCase();
  if(!q){ fill($("trackList"), [], "Enter your complaint ID and press Search."); return; }
  fill($("trackList"), await getReports({id:q}), "No report found with that ID.");
}
$("find").onclick = renderTrack; $("q").onkeydown = e => { if(e.key==="Enter") renderTrack(); };

async function stats(){
  try{
    const a = await (await fetch("/api/stats")).json();
    $("sTotal").textContent = a.total; $("sOpen").textContent = a.open; $("sDone").textContent = a.resolved;
  }catch(e){}
}
stats();
