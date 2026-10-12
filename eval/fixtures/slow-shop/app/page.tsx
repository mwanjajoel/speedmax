import SearchBox from '../components/SearchBox';

const gallery = ['g1.jpg', 'g2.jpg', 'g3.jpg', 'g4.jpg', 'g5.jpg', 'g6.jpg'];

export default function Home() {
  return (
    <main>
      <img className="hero" src="/hero.png" alt="Summer sale" loading="lazy" />
      <h1>Summer sale</h1>
      <SearchBox />
      <section className="gallery">
        {gallery.map((g) => (
          <img key={g} src={`/img/${g}`} alt="" />
        ))}
      </section>
      <iframe src="https://www.youtube.com/embed/XXXX" width="560" height="315" />
    </main>
  );
}
