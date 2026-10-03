(() => {
  'use strict';
  const menu = document.getElementById('cmseSidebar');
  const trigger = document.getElementById('cmseSidebarBtn');
  if (trigger && menu) {
    const observer = new MutationObserver(() => trigger.setAttribute('aria-expanded', String(document.body.classList.contains('cmse-sidebar-open'))));
    observer.observe(document.body, { attributes:true, attributeFilter:['class'] });
    document.addEventListener('keydown', event => { if(event.key === 'Escape' && document.body.classList.contains('cmse-sidebar-open')) { document.body.classList.remove('cmse-sidebar-open'); trigger.focus(); } });
    trigger.addEventListener('click', () => { if(document.body.classList.contains('cmse-sidebar-open')) menu.querySelector('input,button,a')?.focus(); });
  }
  // Pages without an exact menu link still identify the relevant section.
  if (!document.querySelector('#cmseNav a.active')) {
    const matches = [...document.querySelectorAll('#cmseNav a[data-nav-title]')].filter(a => {
      const path = new URL(a.href).pathname.replace(/\/$/,'');
      return path !== '/' && location.pathname.startsWith(path + '/');
    }).sort((a,b) => b.pathname.length - a.pathname.length);
    const active = matches[0];
    if (active) {
      active.classList.add('active'); active.setAttribute('aria-current','page');
      const section = active.closest('.collapse');
      if(section) { section.classList.add('show'); document.querySelector('[data-bs-target="#' + section.id + '"]')?.setAttribute('aria-expanded','true'); }
    }
  }
  document.querySelectorAll('#cmseNav a.active').forEach(a => a.setAttribute('aria-current','page'));
  const heading = document.querySelector('#cmseMainContent h2');
  const breadcrumb = document.getElementById('cmseBreadcrumbCurrent');
  if(heading && breadcrumb && !document.querySelector('#cmseNav a.active')) breadcrumb.textContent = heading.textContent.trim();
  document.querySelectorAll('.badge').forEach(badge => {
    const value = badge.textContent.trim().toLowerCase();
    if(['approved','paid','completed','closed','active'].includes(value)) badge.classList.add('erp-status-good');
    else if(['submitted','under review','pending','pending manager approval','pending finance approval','partially paid','need correction'].includes(value)) badge.classList.add('erp-status-pending');
    else if(['rejected','cancelled','critical','delayed'].includes(value)) badge.classList.add('erp-status-danger');
  });
  // Contain wide legacy tables on small screens without changing their contents.
  document.querySelectorAll('#cmseMainContent table').forEach(table => {
    if(!table.closest('.table-responsive') && !table.closest('form')) { const wrapper=document.createElement('div'); wrapper.className='table-responsive'; table.before(wrapper); wrapper.append(table); }
  });
  const form = document.getElementById('erpRecordForm');
  if(form) {
    const fields=[...form.querySelectorAll('[data-completion-field]')];
    const update=()=>{ const complete=fields.filter(field=>field.value.trim()).length; const label=document.getElementById('erpFieldsComplete'); if(label) label.textContent=complete + ' of ' + fields.length + ' fields filled'; const bar=document.getElementById('erpFieldsProgress'); if(bar) bar.style.width=(fields.length ? complete/fields.length*100 : 0)+'%'; };
    form.addEventListener('input',update); form.addEventListener('change',update); update();
    const project=form.querySelector('[name=project_id]');
    const customer=document.getElementById('erpProjectCustomer');
    const updateCustomer=()=>{ if(customer) customer.textContent=project.selectedOptions[0]?.dataset.customer ? 'Customer: '+project.selectedOptions[0].dataset.customer : 'Choose a project to link its customer.'; };
    if(project){ project.addEventListener('change',updateCustomer); updateCustomer(); }
    const outline=[...form.querySelectorAll('.erp-form-outline a')];
    if('IntersectionObserver' in window) { const sections=new IntersectionObserver(entries=>{ entries.forEach(entry=>{if(entry.isIntersecting){outline.forEach(a=>a.classList.toggle('active',a.hash==='#'+entry.target.id));}}); },{rootMargin:'-130px 0px -55% 0px'}); form.querySelectorAll('.erp-form-section').forEach(section=>sections.observe(section)); }
  }
  const passwordButton=document.getElementById('erpPasswordToggle');
  if(passwordButton){ passwordButton.addEventListener('click',()=>{ const input=document.getElementById('loginPassword'); const reveal=input.type==='password'; input.type=reveal?'text':'password'; passwordButton.textContent=reveal?'Hide':'Show'; passwordButton.setAttribute('aria-pressed',String(reveal)); }); }
})();
