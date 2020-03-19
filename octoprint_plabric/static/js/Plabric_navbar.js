$(function() {
    function NavbarViewModel(parameters) {
        var self = this;

        self.settings = parameters[0];
        self.status = ko.observable(plabric_status.status);
        self.status_color = ko.observable(plabric_status.status_color);
        self.step = ko.observable(plabric_status.step);
        setStatusColor();

        self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin !== "Plabric") {
                return;
            }
            else {
                self.step(data.step);
                self.status(data.status);
                setStatusColor();
            }
        };

        function setStatusColor() {
            if(self.step() === 'connected'){
                self.status_color('#00A69A');
            }else if(self.step() === 'ready'){
                self.status_color('#ff8f00');
            }else{
                self.status_color('#f50057');
            }
        }
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: NavbarViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#navbar_plugin_plabric",]
    });
});
