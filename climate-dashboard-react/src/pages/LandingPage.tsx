import { Link } from 'react-router-dom';
import { Button } from 'design-system';

// Structural placeholder for Release 20 (SPEC.md §5.25): this PR lands the route, layout and nav.
// The real page -- hero + globe, story cards, ranking race, feature cards -- follows in the
// landing-page PR, so this is deliberately minimal and not to be deployed on its own.
export default function LandingPage() {
  return (
    <div style={{ padding: 'clamp(24px, 5.5vw, 80px)' }}>
      <h1 className="__s9cmpx-headline2" style={{ margin: 0 }}>Where the world’s CO₂ comes from — and where it’s heading.</h1>
      <p className="__s9cmpx-body1" style={{ margin: '16px 0 24px', color: 'var(--__s9cmpx-static-text-weak)' }}>
        Thirty-five years of emissions, regression trend models, ETS(A,Ad,N) forecasts to 2043 and scenario pathways to 2040.
      </p>
      <Link to="/overview" style={{ textDecoration: 'none' }}>
        <Button variant="primary">Explore the data</Button>
      </Link>
    </div>
  );
}
