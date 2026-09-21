import Navbar from './components/Navbar';
import Hero from './components/Hero';
import Stats from './components/Stats';
import Features from './components/Features';
import AgencyMatrix from './components/AgencyMatrix';
import SetupGuide from './components/SetupGuide';
import Footer from './components/Footer';

function App() {
  return (
    <div className="flex flex-col min-h-screen">
      <Navbar />
      <main>
        <Hero />
        <Stats />
        <Features />
        <AgencyMatrix />
        <SetupGuide />
      </main>
      <Footer />
    </div>
  );
}

export default App;