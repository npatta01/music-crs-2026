window.addEventListener('load',()=>setTimeout(()=>{
  const P=document.getElementById('poster').getBoundingClientRect();
  const out=[...document.querySelectorAll('.col')].map((c,i)=>{
    const r=c.getBoundingClientRect(); let maxb=0;
    c.querySelectorAll('*').forEach(e=>{maxb=Math.max(maxb,e.getBoundingClientRect().bottom)});
    return `col${i}: content-bottom ${(maxb-P.top).toFixed(0)} / poster ${P.height.toFixed(0)} px, slack ${((P.bottom-maxb)/P.height*841).toFixed(1)}mm`;
  });
  document.body.setAttribute('data-probe',out.join(' | '));
},500));
