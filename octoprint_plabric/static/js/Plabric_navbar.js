$(function() {
    function NavbarViewModel(parameters) {
        var self = this;

        self.settings = parameters[0];
        self.status = ko.observable(plabric_status.status);
        self.status_color = ko.observable(plabric_status.status_color);
        setStatusColor();

        self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin !== "Plabric") {
                return;
            }
            else {
                self.status(data.status);
                setStatusColor();
            }
        };

        function setStatusColor() {
            if(self.status() === 'Disconnected' || self.status() === 'Not running' || self.status() === 'Login needed' || self.status() === 'Need install' || self.status() == 'Stopped'){
                self.status_color('#f50057');
            }else if(self.status() === 'Ready'){
                self.status_color('#ff8f00');
            }else{
                self.status_color('#00A69A');
            }
        }
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: NavbarViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#navbar_plugin_plabric",]
    });
});
