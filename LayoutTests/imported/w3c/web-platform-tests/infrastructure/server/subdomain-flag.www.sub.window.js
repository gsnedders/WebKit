test(() => {
  assert_equals(location.hostname, "{{hosts[alt][]}}");
}, "Use of .www. file name flag implies www subdomain");

done();
