tocbot.init({
  // Where to render the table of contents.
  tocSelector: '.js-toc',
  // Where to grab the headings to build the table of contents.
  contentSelector: '.js-toc-content',
  // Which headings to grab inside of the contentSelector element.
  headingSelector: 'h2, h3',
  // For headings inside relative or absolute positioned containers within content.
  hasInnerContainers: true,

  positionFixedSelector: '#usersuite-sidebar-nav',
  extraLinkClasses: 'text-decoration-none'
});

// Enable popovers, see https://getbootstrap.com/docs/5.3/components/popovers/
const popoverTriggerList = document.querySelectorAll('[data-bs-toggle="popover"]');
const popoverList = [...popoverTriggerList].map(popoverTriggerEl => new bootstrap.Popover(popoverTriggerEl));
