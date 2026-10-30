-- Запускает экспорт всех дорожек в открытом проекте Logic. Спайк 2, только контрольный проект.
-- Черновик: ни разу не запускался, нет разрешения Accessibility. Имя пункта меню не подтверждено.
-- Не проверяет, какой проект открыт, сам нажимает Replace, а готовность считает по числу WAV в папке.
-- Настройки и шаблон имён берутся из диалога, где они заданы вручную.
--
--     osascript spikes/logic_export/export_all.applescript <папка> <число файлов>
--
-- Нужно разрешение Accessibility. Папка должна уже быть выбрана в диалоге: скрипт её не меняет.

on run argv
	set targetFolder to item 1 of argv
	set expected to (item 2 of argv) as integer
	tell application "Logic Pro X" to activate
	delay 1
	tell application "System Events"
		tell process "Logic Pro X"
			set exportMenu to menu 1 of menu item "Export" of menu 1 of menu bar item "File" of menu bar 1
			set found to false
			repeat with candidate in menu items of exportMenu
				if name of candidate starts with "All Tracks" then
					click candidate
					set found to true
					exit repeat
				end if
			end repeat
			if not found then error "нет пункта All Tracks в меню Export"
			repeat 50 times
				if (count of sheets of front window) > 0 then exit repeat
				if exists button "Export" of front window then exit repeat
				delay 0.2
			end repeat
			if (count of sheets of front window) > 0 then
				click button "Export" of sheet 1 of front window
			else
				click button "Export" of front window
			end if
			delay 1
			if (count of sheets of front window) > 0 then
				if exists button "Replace" of sheet 1 of front window then
					click button "Replace" of sheet 1 of front window
				end if
			end if
		end tell
	end tell
	repeat 600 times
		set total to (do shell script "ls " & quoted form of targetFolder & " | grep -ci '\\.wav$' || true") as integer
		if total ≥ expected then return "готово: " & total & " файлов"
		delay 1
	end repeat
	error "за 10 минут не появилось " & expected & " файлов"
end run
