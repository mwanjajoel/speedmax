const form = document.getElementById('contact');
const status = document.getElementById('status');

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const button = form.querySelector('button');
  button.disabled = true;
  status.textContent = 'Sending…';
  const res = await fetch('https://formspree.example/f/xyz', { method: 'POST', body: new FormData(form) });
  status.textContent = res.ok ? 'Thanks! We will reply soon.' : 'Something went wrong. Please try again.';
  button.disabled = false;
});
