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
        self.configurated = ko.observable(plabric_variables.configurated);
        self.config_cancelled = ko.observable(plabric_variables.config_cancelled);
        self.temp_token = ko.observable(plabric_variables.temp_token);
        self.docker_running = ko.observable(plabric_variables.docker_running);
        self.docker_available = ko.observable(plabric_variables.docker_available);
        self.socket_connected = ko.observable(plabric_variables.socket_connected);
        self.os = ko.observable(plabric_variables.os);
        self.machine = ko.observable(plabric_variables.machine);
        self.installing = ko.observable(plabric_variables.installing);
        self.install_progress = ko.observable(plabric_variables.install_progress);
        self.progress_width = ko.observable('0px');
        self.error = ko.observable(plabric_variables.error);

        self.login = function () {
            $.ajax({
                type: "GET",
                url: "/plugin/Plabric/authorize",
                success: function (data) {
                    console.log("Plabric: Waiting for authorization");
                },
                error: function (error) {
                    console.error("Plabric: Unable to retrieve token");
                }
            });
        };

        self.onDataUpdaterPluginMessage = function (plugin, data) {
            if (plugin !== "Plabric") {
                return;
            } else {
                self.configurated(data.configurated);
                self.config_cancelled(data.config_cancelled);
                self.docker_available(data.docker_available);
                self.docker_running(data.docker_running);
                self.temp_token(data.temp_token);
                self.docker_running(data.docker_running);
                self.socket_connected(data.socket_connected);
                self.os(data.os);
                self.machine(data.machine);
                self.installing(data.installing);
                self.install_progress(data.install_progress);
                self.progress_width(self.install_progress().toString() + '%');
                self.error(data.error);

                if (self.config_cancelled()) {
                    self.cancel_config();
                }
            }
        };

        self.disable = function () {
            $.ajax({
                type: "GET",
                url: "/plugin/Plabric/disable",
                success: function (data) {
                    self.configurated(false);
                    self.temp_token(false);
                },
                error: function (error) {
                    console.error("Plabric: Unable to retrieve register status");
                }
            });
        };

        self.cancel_config = function () {
            self.temp_token(null);
        };

        self.run_docker = function () {
            $.ajax({
                type: "GET",
                url: "/plugin/Plabric/run_docker",
                success: function (data) {
                },
                error: function (error) {
                    console.error("Plabric: Unable to run docker");
                }
            });
        };

        self.reconnect = function () {
            $.ajax({
                type: "GET",
                url: "/plugin/Plabric/reconnect",
                success: function (data) {
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
