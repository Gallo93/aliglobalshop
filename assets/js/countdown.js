(function(){
  "use strict";
  function pad(n){return n<10?"0"+n:String(n);}
  function render(el,ms){
    if(ms<=0){
      el.textContent="Ended";
      el.classList.add("countdown--expired");
      return false;
    }
    var s=Math.floor(ms/1000);
    var d=Math.floor(s/86400);s%=86400;
    var h=Math.floor(s/3600);s%=3600;
    var m=Math.floor(s/60);s%=60;
    var parts=[];
    if(d>0) parts.push(d+"d");
    parts.push(pad(h)+":"+pad(m)+":"+pad(s));
    el.textContent=parts.join(" ");
    return true;
  }
  function init(){
    var nodes=document.querySelectorAll("[data-expires]");
    if(!nodes.length) return;
    var items=[];
    nodes.forEach(function(el){
      var raw=el.getAttribute("data-expires");
      if(!raw) return;
      var t=Date.parse(raw);
      if(isNaN(t)) return;
      el.classList.add("countdown");
      items.push({el:el,target:t});
    });
    if(!items.length) return;
    function tick(){
      var now=Date.now();
      items=items.filter(function(it){
        return render(it.el,it.target-now);
      });
    }
    tick();
    setInterval(tick,1000);
  }
  if(document.readyState==="loading"){
    document.addEventListener("DOMContentLoaded",init);
  } else { init(); }
})();
