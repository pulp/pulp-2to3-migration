window.onload = function() {
    var elem = document.createElement('div');
    var body = document.getElementsByClassName("bodywrapper")[0]
    var doc = document.getElementsByClassName("body")[0]
    elem.className = "admonition important"
    elem.id = "pulp-2to3-migration-eol-banner"
    elem.innerHTML = "<p>This plugin reaches its EOL on December 31, 2022. The last supported pulpcore" +
        " version is 3.19.</p>";
    body.insertBefore(elem, doc)
}
