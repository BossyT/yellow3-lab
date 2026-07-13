(function(){
  var E=window.__ECON, calc=document.getElementById('calc');
  if(!E||!calc) return;
  var $=function(id){return document.getElementById(id);};
  var tasks=$('c-tasks'),inp=$('c-inp'),outp=$('c-outp'),cached=$('c-cached'),cv=$('c-cached-v');
  function cost(p,w){
    if(!p||p.in==null||p.out==null) return null;
    var itok=w.tasks*w.inp, otok=w.tasks*w.outp;
    var crp=(p.cache_read!=null?p.cache_read:p.in);
    var unc=itok*(1-w.cached)*p.in, cac=itok*w.cached*crp, out=otok*p.out;
    return {total:unc+cac+out,unc:unc,cac:cac,out:out};
  }
  function money(v){ if(v==null) return '\u2014'; return '$'+(v>=100?v.toFixed(0):v.toFixed(2)); }
  function readW(){ return {tasks:+tasks.value||0,inp:+inp.value||0,outp:+outp.value||0,cached:(+cached.value||0)/100}; }
  function render(){
    var w=readW(); if(cv) cv.textContent=cached.value;
    var r=cost(E.you,w);
    if(r){
      $('c-total').textContent=money(r.total);
      $('c-unc').textContent=money(r.unc); $('c-cac').textContent=money(r.cac); $('c-out').textContent=money(r.out);
      var per=w.tasks>0?r.total/w.tasks:0;
      $('c-per').textContent=(per<1?'$'+per.toFixed(3):money(per))+' per completed task';
    }
    var rows=document.querySelectorAll('#compare .cmp-row'), costs=[];
    (E.compare||[]).forEach(function(c){ var cc=cost(c,w); costs.push(cc?cc.total:null); });
    var valid=costs.filter(function(x){return x!=null;}); var mx=valid.length?Math.max.apply(null,valid):1;
    Array.prototype.forEach.call(rows,function(row,i){
      var t=costs[i], f=row.querySelector('.cmp-fill'), v=row.querySelector('.cmp-val');
      if(f) f.style.width=(t!=null?100*t/mx:0)+'%'; if(v) v.textContent=money(t);
    });
  }
  Array.prototype.forEach.call(document.querySelectorAll('.wl-tab'),function(tab){
    tab.addEventListener('click',function(){
      var w=(E.workloads||{})[tab.getAttribute('data-wl')];
      if(w){ tasks.value=w.tasks; inp.value=w.inp; outp.value=w.outp; cached.value=Math.round(w.cached*100); }
      document.querySelectorAll('.wl-tab').forEach(function(t){t.classList.remove('active');});
      tab.classList.add('active'); render();
    });
  });
  [tasks,inp,outp,cached].forEach(function(el){ if(el) el.addEventListener('input',render); });
  var def=(E.workloads||{})['coding-agent'];
  if(def){ tasks.value=def.tasks; inp.value=def.inp; outp.value=def.outp; cached.value=Math.round(def.cached*100); }
  render();
})();