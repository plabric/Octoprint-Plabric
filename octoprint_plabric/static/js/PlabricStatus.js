
$(function() {
    function PlabricStatusViewModel() {
        var self = this;

        self.plabric_token = ko.observable(null);
        self.step = ko.observable(null);
        self.error = ko.observable('');
        self.loading = ko.observable(false);
        self.status = ko.observable(null);
        self.status_color = ko.observable(null);

        self.refreshState = function(state) {
            self.plabric_token(state.plabric_token);
            self.step(state.step);
            self.error(state.error);
            self.loading(state.loading);
            self.status(state.status);
            setStatusColor();
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

        self.onDataUpdaterPluginMessage = function (plugin, data) {
            if (plugin !== "Plabric") {
                return;
            } else {
                self.refreshState(data)
            }
        };

        self.onStartup = self.onServerReconnect = self.onUserLoggedIn = self.onUserLoggedOut = function() {
            self.requestData();
        };

        self.requestData = function () {
            $.ajax({
                type: "GET",
                url: "/plugin/Plabric/data",
                dataType: "json",
                contentType: "application/json",
                success: function (data) {
                    console.log("Plabric: Status data received");
                    self.refreshState(data);
                },
                error: function (error) {
                    console.error("Plabric: Unable to retrieve status data");
                }
            });
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: PlabricStatusViewModel,
        dependencies: [],
        elements: []
    });
});
