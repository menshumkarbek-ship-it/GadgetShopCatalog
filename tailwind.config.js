/**
 * Builds shop/static/shop/css/site.css, the one stylesheet every page loads.
 *
 * Rebuild after changing classes in any template or in shop/*.py (the
 * management forms set their input classes there):
 *
 *     npm run build:css
 *
 * The built file is committed, so deploying needs no Node. CI rebuilds it and
 * fails if the committed copy is out of date.
 */
module.exports = {
  content: [
    './templates/**/*.html',
    './shop/templates/**/*.html',
    './shop/**/*.py',
    // The tests name old classes only to assert they are gone.
    '!./shop/tests.py',
  ],
  theme: {
    extend: {
      // Design tokens from DESIGN.md. Names avoid Tailwind's own scale names
      // (slate, indigo, sky…) so nothing that still relies on the defaults —
      // the management panel does — is disturbed.
      colors: {
        ink: '#1d1d1f',
        midgray: '#707070',
        deepgray: '#474747',
        hairline: '#d6d6d6',
        canvas: '#f5f5f7',
        paper: '#ffffff',
        coolwash: '#e8e8ed',
        faded: '#fafafc',
        quietdot: '#777779',
        electric: '#0071e3',
        linkblue: '#0066cc',
        ember: '#b64400',
      },
      borderRadius: {
        card: '28px',
        pill: '980px',
      },
      maxWidth: {
        page: '1200px',
      },
    },
  },
  plugins: [],
};
