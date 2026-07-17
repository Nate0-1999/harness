function App() {
  return (
    <div className="shell">
      <header className="shell__header">
        <div className="brand" aria-label="Harness home">
          <span className="brand__mark" aria-hidden="true" />
          <span>Harness</span>
        </div>
        <span className="status">
          <span className="status__dot" aria-hidden="true" />
          Foundation ready
        </span>
      </header>

      <main className="shell__main">
        <section className="welcome" aria-labelledby="welcome-title">
          <p className="welcome__eyebrow">Bootstrap shell</p>
          <h1 id="welcome-title">A clear surface for what comes next.</h1>
          <p className="welcome__body">
            The responsive web foundation is in place. Product capabilities
            will arrive in their own milestone packets.
          </p>
          <div className="welcome__note">
            <span aria-hidden="true">01</span>
            <p>Scaffold only · no product behavior is active</p>
          </div>
        </section>
      </main>

      <footer className="shell__footer">
        <span>M1</span>
        <span>Agent Zero</span>
      </footer>
    </div>
  )
}

export default App
