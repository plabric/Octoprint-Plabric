$(function() {
    function NavbarViewModel(parameters) {
        var self = this;
        self.plabric = parameters[0];
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: NavbarViewModel,
        dependencies: ["plabricStatusViewModel"],
        elements: ["#navbar_plugin_plabric"]
    });
});
