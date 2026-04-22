# Outreach: Roy Levy

**To:** hello@roylevy.dev
**Subject:** Manifest V3 post-mortem from a hover-zoom extension

**Send window:** Tue-Thu, 9-11am IDT

---

Hi Roy,

Reader of your Medium writing on web dev — always appreciate when senior engineers share the ugly parts of real-world decisions rather than the polished retrospective.

I lead engineering on Ultra Zoom, a hover-to-zoom browser extension we rebuilt from the ground up for Manifest V3. A lot of hover-zoom extensions didn't make the MV3 transition cleanly — some broke outright, others resorted to remote code and dynamic rules that defeat the point of the new security model. I wrote up what we learned about the architectural choices MV3 forces on this class of extension:
https://ultrazoom.app/blog/manifest-v3-trap

A couple of companion posts you might find interesting as case-study material:
- Line-by-line bundle breakdown for a 60+ site content script: https://ultrazoom.app/blog/bundle-budget
- Why we picked Preact over React and what the migration cost actually was: https://ultrazoom.app/blog/preact-over-react

If any of that would land with your audience — whether as a case study, a source for a future piece, or just a link in something you're already working on — I'd be glad to go deeper on any of the decisions. No hard ask either way.

Best,
[Your Name]
Lost Rabbit Digital LLC
https://ultrazoom.app
