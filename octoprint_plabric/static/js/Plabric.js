/*
 * View model for Plabric
 *
 * Author: Plabric
 * License: AGPLv3
 */
$(function() {
    function PlabricViewModel(parameters) {
        var self = this;
        self.plabric = parameters[0];

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
        dependencies: ["plabricStatusViewModel"],
        elements: ["#settings_plugin_Plabric"]
    });
});
