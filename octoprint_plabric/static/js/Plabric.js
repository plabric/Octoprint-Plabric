/*
 * View model for Plabric
 *
 * Author: Plabric
 * License: AGPLv3
 */
$(function() {
    function PlabricViewModel(parameters) {
        var self = this;

        self.settings = parameters[0];
        self.plabric_token = ko.observable(plabric_variables.plabric_token);
        self.step = ko.observable(plabric_variables.step);
        self.error = ko.observable(plabric_variables.error);
        self.loading = ko.observable(plabric_variables.loading);

        self.onDataUpdaterPluginMessage = function (plugin, data) {
            if (plugin !== "Plabric") {
                return;
            } else {
                self.plabric_token(data.plabric_token);
                self.step(data.step);
                self.error(data.error);
                self.loading(data.loading);
            }
        };

        self.login = function () {
            $.ajax({
                type: "POST",
                url: "/plugin/Plabric/authorize",
                success: function (data) {
                    console.log("Plabric: Waiting for authorization");
                },
                error: function (error) {
                    console.error("Plabric: Unable to retrieve token");
                }
            });
        };

        self.disable = function () {
            $.ajax({
                type: "POST",
                url: "/plugin/Plabric/disable",
                success: function (data) {
                    console.log("Plabric: Disable request sent");
                },
                error: function (error) {
                    console.error("Plabric: Unable to retrieve register status");
                }
            });
        };

        self.reconnect = function () {
            $.ajax({
                type: "POST",
                url: "/plugin/Plabric/reconnect",
                success: function (data) {
                    console.log("Plabric: Reconnection request sent");
                },
                error: function (error) {
                    console.error("Plabric: Unable to connect");
                }
            });
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: PlabricViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#settings_plugin_Plabric"]
    });
});
