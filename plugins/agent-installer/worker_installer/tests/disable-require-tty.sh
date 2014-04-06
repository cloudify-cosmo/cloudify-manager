# now modify sudoers configuration to allow execution without tty
grep -i ubuntu /proc/version > /dev/null
if [ "$?" -eq "0" ]; then
	# ubuntu
	echo Running on Ubuntu
	if sudo grep -q -E '[^!]requiretty' /etc/sudoers; then
		echo Creating sudoers user file
		echo "Defaults:`whoami` !requiretty" | sudo tee /etc/sudoers.d/`whoami` >/dev/null
		sudo chmod 0440 /etc/sudoers.d/`whoami`
	else
		echo No requiretty directive found, nothing to do
	fi
else
	# other - modify sudoers file
	if [ ! -f "/etc/sudoers" ]; then
		error_exit 116 "Could not find sudoers file at expected location (/etc/sudoers)"
	fi
	echo Setting privileged mode
	sudo sed -i 's/^Defaults.*requiretty/#&/g' /etc/sudoers || error_exit_on_level $? 117 "Failed to edit sudoers file to disable requiretty directive" 1
fi